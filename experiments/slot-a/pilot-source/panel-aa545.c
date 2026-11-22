#include <linux/clk.h>
// SPDX-License-Identifier: GPL-2.0-only
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/regulator/consumer.h>
#include <drm/display/drm_dsc_helper.h>
#include <drm/drm_connector.h>
#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>

struct aa545 {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi;
	struct drm_dsc_config dsc;
	struct regulator *vddio;
	struct regulator *vci;
	struct gpio_desc *reset;
	struct gpio_desc *iris_ready;
	struct gpio_desc *iris_power;
	struct gpio_desc *iris_wakeup;
	struct gpio_desc *iris_reset;
	struct clk *iris_ref;
	bool iris_ref_enabled;
};

struct aa545_packet {
	u8 type;
	u8 delay;
	u8 length;
	const u8 *payload;
};

#include "aa545-packets.h"

static int aa545_send(struct aa545 *ctx, const struct aa545_packet *packets,
		      size_t count, bool low_power)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	size_t i;

	for (i = 0; i < count; i++) {
		struct mipi_dsi_msg msg = {
			.channel = dsi->channel,
			.type = packets[i].type,
			.flags = low_power ? MIPI_DSI_MSG_USE_LPM : 0,
			.tx_len = packets[i].length,
			.tx_buf = packets[i].payload,
		};
		ssize_t result = dsi->host->ops->transfer(dsi->host, &msg);

		if (result < 0)
			return dev_err_probe(&dsi->dev, result,
					     "DSI packet %zu, command 0x%02x\n",
					     i, packets[i].payload[0]);
		if (packets[i].delay)
			fsleep(packets[i].delay * 1000);
	}

	return 0;
}

static void aa545_disable_iris_ref(struct aa545 *ctx)
{
	if (ctx->iris_ref_enabled) {
		clk_disable_unprepare(ctx->iris_ref);
		ctx->iris_ref_enabled = false;
	}
}

static void aa545_power_off(struct aa545 *ctx)
{
	aa545_disable_iris_ref(ctx);
	gpiod_set_value_cansleep(ctx->reset, 1);
	fsleep(1000);
	regulator_disable(ctx->vci);
	fsleep(30000);
	regulator_disable(ctx->vddio);
}

static int aa545_prepare(struct drm_panel *panel)
{
	struct aa545 *ctx = container_of(panel, struct aa545, panel);
	struct drm_dsc_picture_parameter_set pps;
	unsigned long flags;
	int ret;

	ret = regulator_enable(ctx->vddio);
	if (ret)
		return ret;

	{
		int power_before = gpiod_get_value_cansleep(ctx->iris_power);
		int wake_before = gpiod_get_value_cansleep(ctx->iris_wakeup);
		int power_dir = gpiod_get_direction(ctx->iris_power);
		int wake_dir = gpiod_get_direction(ctx->iris_wakeup);

		ret = gpiod_direction_output(ctx->iris_power, 1);
		if (ret) {
			regulator_disable(ctx->vddio);
			return ret;
		}

		dev_info(panel->dev,
			 "AA545 Iris PMIC power=%d(dir=%d)->%d wake=%d(dir=%d)\n",
			 power_before, power_dir,
			 gpiod_get_value_cansleep(ctx->iris_power), wake_before, wake_dir);
	}

	fsleep(5000);
	ret = clk_prepare_enable(ctx->iris_ref);
	if (ret) {
		regulator_disable(ctx->vddio);
		return ret;
	}
	ctx->iris_ref_enabled = true;
	dev_info(panel->dev, "AA545 Iris reference clock enabled rate=%lu\n",
		 clk_get_rate(ctx->iris_ref));
	fsleep(5000);
	ret = gpiod_get_value_cansleep(ctx->iris_ready);
	dev_info(panel->dev, "AA545 Iris bypass ready=%d\n", ret);
	if (ret < 0) {
		aa545_disable_iris_ref(ctx);
		regulator_disable(ctx->vddio);
		return ret;
	}

	ret = regulator_enable(ctx->vci);
	if (ret) {
		aa545_disable_iris_ref(ctx);
		regulator_disable(ctx->vddio);
		return ret;
	}

	fsleep(15000);
	{
		u8 power = 0;
		int reset_level = gpiod_get_raw_value_cansleep(ctx->reset);
		ssize_t length = 0;

		if (reset_level == 1) {
			dev_info(panel->dev, "AA545 pre-reset read begin\n");
			flags = ctx->dsi->mode_flags;
			ctx->dsi->mode_flags = flags | MIPI_DSI_MODE_LPM;
			length = mipi_dsi_dcs_read(ctx->dsi, 0x0a, &power, sizeof(power));
			ctx->dsi->mode_flags = flags;
		}
		dev_info(panel->dev, "AA545 pre-reset gpio=%d DCS 0a=%02x len=%zd\n",
			 reset_level, power, length);
	}
	if (gpiod_get_raw_value_cansleep(ctx->reset) == 1) {
		u8 hs_power = 0;
		ssize_t hs_len;

		flags = ctx->dsi->mode_flags;
		ctx->dsi->mode_flags = flags & ~MIPI_DSI_MODE_LPM;
		hs_len = mipi_dsi_dcs_read(ctx->dsi, 0x0a, &hs_power, sizeof(hs_power));
		ctx->dsi->mode_flags = flags;
		dev_info(panel->dev, "AA545 pre-reset FIFO HS 0a=%02x len=%zd\n", hs_power, hs_len);

		if (hs_len == 1 && hs_power == 0x9c) {
			dev_info(panel->dev, "AA545 keeping the verified firmware panel setup\n");
			return 0;
		}

	}

	ret = gpiod_direction_output(ctx->iris_wakeup, 0);
	if (ret)
		goto power_off;
	{
		u8 power = 0;
		ssize_t length;
		int ready_asserted, ready_released;

		ret = gpiod_direction_output(ctx->iris_reset, 1);
		if (ret)
			goto power_off;
		usleep_range(1000, 1100);
		ready_asserted = gpiod_get_value_cansleep(ctx->iris_ready);
		gpiod_set_value_cansleep(ctx->iris_reset, 0);
		usleep_range(2000, 2100);
		ready_released = gpiod_get_value_cansleep(ctx->iris_ready);

		flags = ctx->dsi->mode_flags;
		ctx->dsi->mode_flags = flags | MIPI_DSI_MODE_LPM;
		length = mipi_dsi_dcs_read(ctx->dsi, 0x0a, &power, sizeof(power));
		ctx->dsi->mode_flags = flags;
		dev_info(panel->dev,
			 "AA545 Iris reset ready=%d->%d DCS 0a=%02x len=%zd\n",
			 ready_asserted, ready_released, power, length);
	}

	ret = gpiod_direction_output(ctx->reset, 0);
	if (ret)
		goto power_off;

	fsleep(10000);
	gpiod_set_value_cansleep(ctx->reset, 1);
	fsleep(5000);
	gpiod_set_value_cansleep(ctx->reset, 0);
	fsleep(30000);

	ret = aa545_send(ctx, aa545_on, ARRAY_SIZE(aa545_on), true);
	if (ret)
		goto power_off;
	drm_dsc_pps_payload_pack(&pps, &ctx->dsc);
	flags = ctx->dsi->mode_flags;
	ctx->dsi->mode_flags = flags | MIPI_DSI_MODE_LPM;
	ret = mipi_dsi_picture_parameter_set(ctx->dsi, &pps);
	ctx->dsi->mode_flags = flags;
	dev_info(panel->dev, "AA545 low-power PPS result=%d\n", ret);
	if (ret < 0)
		goto power_off;

	dev_info(panel->dev, "AA545 60 Hz initialization sequence sent\n");
	return 0;

power_off:
	aa545_power_off(ctx);
	return ret;
}

static void aa545_read_status(struct aa545 *ctx)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	unsigned long flags = dsi->mode_flags;
	u8 power = 0, status = 0;
	const u8 esd_page[] = { 0xff, 0x08, 0x58, 0x20 };
	const u8 default_page[] = { 0xff, 0x08, 0x58, 0x00 };
	ssize_t power_len, status_len, ret;

	dsi->mode_flags = flags | MIPI_DSI_MODE_LPM;
	ret = mipi_dsi_dcs_write_buffer(dsi, esd_page, sizeof(esd_page));
	dev_info(&dsi->dev, "AA545 status page 0x20 transmit=%zd\n", ret);
	if (ret < 0) {
		dsi->mode_flags = flags;
		return;
	}

	power_len = mipi_dsi_dcs_read(dsi, 0x0a, &power, sizeof(power));
	status_len = mipi_dsi_dcs_read(dsi, 0xb0, &status, sizeof(status));
	ret = mipi_dsi_dcs_write_buffer(dsi, default_page, sizeof(default_page));
	{
		u8 hs_power = 0;
		ssize_t hs_len;

		dsi->mode_flags = flags & ~MIPI_DSI_MODE_LPM;
		hs_len = mipi_dsi_dcs_read(dsi, 0x0a, &hs_power, sizeof(hs_power));
		dev_info(&dsi->dev, "AA545 VT3 host HS 0a=%02x len=%zd\n", hs_power, hs_len);
	}
	dsi->mode_flags = flags;
	dev_info(&dsi->dev, "AA545 restore page 0x00 transmit=%zd\n", ret);

	dev_info(&dsi->dev, "AA545 status 0a=%02x len=%zd b0=%02x len=%zd vt3_match=%d\n",
		 power, power_len, status, status_len,
		 power_len == 1 && status_len == 1 && power == 0x9c &&
		 (status == 0x0f || status == 0x05));
}

static int aa545_enable(struct drm_panel *panel)
{
	struct aa545 *ctx = container_of(panel, struct aa545, panel);
	const u8 brightness[] = { 0x51, 0x05, 0x99 };
	ssize_t ret;

	if (!panel->prepared)
		return -EIO;

	ret = mipi_dsi_dcs_write_buffer(ctx->dsi, brightness, sizeof(brightness));
	if (ret < 0)
		return ret;
	dev_info(panel->dev, "AA545 test brightness enabled\n");
	aa545_disable_iris_ref(ctx);
	aa545_read_status(ctx);
	return 0;
}

static int aa545_unprepare(struct drm_panel *panel)
{
	struct aa545 *ctx = container_of(panel, struct aa545, panel);
	aa545_send(ctx, aa545_off, ARRAY_SIZE(aa545_off), false);
	aa545_power_off(ctx);
	return 0;
}

static int aa545_get_modes(struct drm_panel *panel, struct drm_connector *connector)
{
	static const struct drm_display_mode mode = {
		.clock = 299904,
		.hdisplay = 1440,
		.hsync_start = 1504,
		.hsync_end = 1512,
		.htotal = 1562,
		.vdisplay = 3168,
		.vsync_start = 3184,
		.vsync_end = 3188,
		.vtotal = 3200,
		.width_mm = 71,
		.height_mm = 158,
		.type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED,
	};

	struct drm_display_mode *preferred = drm_mode_duplicate(connector->dev, &mode);

	if (!preferred)
		return -ENOMEM;
	drm_mode_set_name(preferred);
	drm_mode_probed_add(connector, preferred);
	connector->display_info.width_mm = mode.width_mm;
	connector->display_info.height_mm = mode.height_mm;
	return 1;
}

static const struct drm_panel_funcs aa545_panel_funcs = {
	.prepare = aa545_prepare,
	.enable = aa545_enable,
	.unprepare = aa545_unprepare,
	.get_modes = aa545_get_modes,
};

static int aa545_probe(struct mipi_dsi_device *dsi)
{
	struct device *dev = &dsi->dev;
	struct aa545 *ctx;
	int ret;

	ctx = devm_drm_panel_alloc(dev, struct aa545, panel, &aa545_panel_funcs,
				   DRM_MODE_CONNECTOR_DSI);
	if (IS_ERR(ctx))
		return PTR_ERR(ctx);
	ctx->dsi = dsi;
	ctx->vddio = devm_regulator_get(dev, "vddio");
	if (IS_ERR(ctx->vddio))
		return dev_err_probe(dev, PTR_ERR(ctx->vddio), "panel I/O supply\n");
	ctx->vci = devm_regulator_get(dev, "vci");
	if (IS_ERR(ctx->vci))
		return dev_err_probe(dev, PTR_ERR(ctx->vci), "panel analog supply\n");
	ctx->reset = devm_gpiod_get(dev, "reset", GPIOD_ASIS);
	if (IS_ERR(ctx->reset))
		return dev_err_probe(dev, PTR_ERR(ctx->reset), "panel reset\n");
	ctx->iris_ready = devm_gpiod_get(dev, "iris-ready", GPIOD_IN);
	if (IS_ERR(ctx->iris_ready))
		return dev_err_probe(dev, PTR_ERR(ctx->iris_ready), "Iris bypass status\n");

	ctx->iris_power = devm_gpiod_get(dev, "iris-power", GPIOD_ASIS);
	if (IS_ERR(ctx->iris_power))
		return dev_err_probe(dev, PTR_ERR(ctx->iris_power), "Iris PMIC power GPIO\n");

	ctx->iris_wakeup = devm_gpiod_get(dev, "iris-wakeup", GPIOD_ASIS);
	if (IS_ERR(ctx->iris_wakeup))
		return dev_err_probe(dev, PTR_ERR(ctx->iris_wakeup), "Iris PMIC wakeup GPIO\n");

	ctx->iris_reset = devm_gpiod_get(dev, "iris-reset", GPIOD_ASIS);
	if (IS_ERR(ctx->iris_reset))
		return dev_err_probe(dev, PTR_ERR(ctx->iris_reset), "Iris reset GPIO\n");
	ctx->iris_ref = devm_clk_get(dev, "iris-ref");
	if (IS_ERR(ctx->iris_ref))
		return dev_err_probe(dev, PTR_ERR(ctx->iris_ref), "Iris reference clock\n");

	dsi->lanes = 4;
	dsi->format = MIPI_DSI_FMT_RGB101010;
	dsi->mode_flags = MIPI_DSI_CLOCK_NON_CONTINUOUS | MIPI_DSI_MODE_NO_EOT_PACKET;

	dsi->dsc = &ctx->dsc;
	ctx->dsc.dsc_version_major = 1;
	ctx->dsc.dsc_version_minor = 1;
	ctx->dsc.slice_width = 720;
	ctx->dsc.slice_height = 22;
	ctx->dsc.slice_count = 2;
	ctx->dsc.bits_per_component = 10;
	ctx->dsc.bits_per_pixel = 8 << 4;
	ctx->dsc.block_pred_enable = true;

	ctx->panel.prepare_prev_first = true;
	drm_panel_add(&ctx->panel);
	mipi_dsi_set_drvdata(dsi, ctx);

	ret = mipi_dsi_attach(dsi);
	if (ret) {
		drm_panel_remove(&ctx->panel);
		return dev_err_probe(dev, ret, "attaching panel to DSI\n");
	}
	dev_info(dev, "AA545 attached, four lanes, WQHD 60 Hz command mode\n");
	return 0;
}

static void aa545_remove(struct mipi_dsi_device *dsi)
{
	struct aa545 *ctx = mipi_dsi_get_drvdata(dsi);

	mipi_dsi_detach(dsi);
	drm_panel_remove(&ctx->panel);
}

static const struct of_device_id aa545_of_match[] = {
	{ .compatible = "samsung,aa545-p-3-a0005" },
	{ }
};
MODULE_DEVICE_TABLE(of, aa545_of_match);

static struct mipi_dsi_driver aa545_driver = {
	.probe = aa545_probe,
	.remove = aa545_remove,
	.driver = {
		.name = "panel-aa545",
		.of_match_table = aa545_of_match,
	},
};
module_mipi_dsi_driver(aa545_driver);

MODULE_LICENSE("GPL");
