from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
if path.name == 'font_ter16x32.c':
    import re
    start = source.index('}, {') + 4
    end = source.index('} };', start)
    original = bytes(int(b, 16) for b in re.findall(r'0x[0-9a-f]{2}', source[start:end]))
    assert len(original) == 256 * 32 * 2
    scaled = bytearray()
    for offset in range(0, len(original), 2):
        row = int.from_bytes(original[offset:offset + 2], 'big')
        doubled = 0
        for bit in range(15, -1, -1):
            doubled = (doubled << 2) | (3 if row & (1 << bit) else 0)
        scaled.extend(doubled.to_bytes(4, 'big') * 2)
    assert len(scaled) == 256 * 64 * 4
    rows = ['\t' + ''.join(f'0x{byte:02x}, ' for byte in scaled[i:i+8]).rstrip()
            for i in range(0, len(scaled), 8)]
    source = (source[:start] + '\n' + '\n'.join(rows) + '\n' + source[end:])
    source = source.replace('FONTDATAMAX 16384', f'FONTDATAMAX {len(scaled)}')
    source = source.replace('"TER16x32"', '"TER32x64"')
    source = source.replace('.width\t= 16', '.width\t= 32').replace('.height = 32', '.height = 64')
    path.write_text(source)
    sys.exit(0)

if path.name == 'clk-rpmh.c':
    anchor = 'DEFINE_CLK_RPMH_VRM(div_clk1, _div2, "divclka1", 2);'
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor +
                            '\nDEFINE_CLK_RPMH_VRM(div_clk1, _sm8650, "clka11", 1);')
    anchor = 'static struct clk_hw *sm8650_rpmh_clocks[] = {\n'
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor +
                            '\t[RPMH_DIV_CLK1] = &clk_rpmh_div_clk1_sm8650.hw,\n')
    path.write_text(source)
    sys.exit(0)

start = source.index('static void dsi_update_dsc_timing(')
source = source[:start] + '''static u32 dsi_dsc_slices_per_packet(struct msm_dsi_host *host)
{
	u32 slices;

	if (!of_property_read_u32(host->pdev->dev.of_node,
				  "qcom,dsc-slices-per-packet", &slices) &&
	    slices == 2 && !(host->dsc->slice_count % slices))
		return slices;

	return 1;
}

''' + source[start:]
start = source.index('\t/* first calculate dsc parameters')
end = source.index('\tif (is_cmd_mode)', start)
source = source[:start] + '''	u32 slices_per_packet = dsi_dsc_slices_per_packet(msm_host);

	slice_per_intf = dsc->slice_count;
	total_bytes_per_intf = dsc->slice_chunk_size * slice_per_intf;
	bytes_per_pkt = dsc->slice_chunk_size * slices_per_packet;
	eol_byte_num = total_bytes_per_intf % 3;
	pkt_per_line = slice_per_intf / slices_per_packet;

''' + source[end:]
start = source.index('\t\t\t/*\n\t\t\t * When DSC is enabled, WC')
end = source.index('\n\n', source.index('wc = msm_host->dsc->slice_chunk_size + 1;', start))
source = source[:start] + '''			wc = msm_host->dsc->slice_chunk_size *
			     dsi_dsc_slices_per_packet(msm_host) + 1;''' + source[end:]
old = """	/* DPU supports only pre-SCR panels */
	ret = drm_dsc_setup_rc_params(dsc, DRM_DSC_1_1_PRE_SCR);"""
new = """	/* DSC 1.1 SCR1 uses the same RGB rate table as DSC 1.2. */

	use_scr1 = of_property_read_bool(msm_host->pdev->dev.of_node,
					 "qcom,dsc-scr1");
	ret = drm_dsc_setup_rc_params(dsc, use_scr1 ? DRM_DSC_1_2_444 :
				      DRM_DSC_1_1_PRE_SCR);"""
assert source.count(old) == 1
source = source.replace(old, new)
source = source.replace("""	dsc->initial_scale_value = drm_dsc_initial_scale_value(dsc);""", """	if (use_scr1)
		dsc->first_line_bpg_offset = 15;

	dsc->initial_scale_value = drm_dsc_initial_scale_value(dsc);""")
anchor = "static int dsi_populate_dsc_params(struct msm_dsi_host *msm_host, struct drm_dsc_config *dsc)\n{"
assert source.count(anchor) == 1
source = source.replace(anchor, anchor + "\n	bool use_scr1;")

source = source.replace('#include <linux/interrupt.h>', '#include <linux/interrupt.h>\n#include <linux/iopoll.h>')
source = source.replace('struct completion dma_comp;', 'struct completion dma_comp;\n\tu32 aa545_rx_irq;')
anchor = 'isr = dsi_read(msm_host, REG_DSI_INTR_CTRL);'
assert source.count(anchor) == 1
source = source.replace(anchor, anchor + """
	if (isr & DSI_IRQ_BTA_DONE)
		WRITE_ONCE(msm_host->aa545_rx_irq, isr);""")
anchor = '\t\tret = dsi_cmds2buf_tx(msm_host, msg);'
assert source.count(anchor) == 1
source = source.replace(anchor, """
		if (short_response && msg->type == MIPI_DSI_DCS_READ && msg->tx_len == 1 &&
		    msg->rx_len == 1 && !msm_host->id &&
		    (*(const u8 *)msg->tx_buf == 0x0a || *(const u8 *)msg->tx_buf == 0xb0))
			WRITE_ONCE(msm_host->aa545_rx_irq, 0);
""" + anchor)
anchor = '\t\tdlen = dsi_cmd_dma_rx(msm_host, buf, rx_byte, pkt_size);'
assert source.count(anchor) == 1
source = source.replace(anchor, """
		if (short_response && msg->type == MIPI_DSI_DCS_READ && msg->tx_len == 1 &&
		    msg->rx_len == 1 && !msm_host->id &&
		    (*(const u8 *)msg->tx_buf == 0x0a || *(const u8 *)msg->tx_buf == 0xb0)) {
			u32 first = dsi_read(msm_host, REG_DSI_RDBK_DATA_CTRL);
			u32 last = first;
			u32 reg[4];
			int wait = 0;

			for (int i = 0; i < ARRAY_SIZE(reg); i++)
				reg[i] = dsi_read(msm_host, REG_DSI_RDBK_DATA(i));
			if (!FIELD(first, DSI_RDBK_DATA_CTRL_COUNT))
				wait = read_poll_timeout(dsi_read, last,
						FIELD(last, DSI_RDBK_DATA_CTRL_COUNT),
						50, 3000, false, msm_host, REG_DSI_RDBK_DATA_CTRL);

			dev_info(&msm_host->pdev->dev,
				 "AA545 RX reg=%02x cnt=%u->%u wait=%d irq=%08x latched=%08x lp_timer=%08x\\n",
				 *(const u8 *)msg->tx_buf, FIELD(first, DSI_RDBK_DATA_CTRL_COUNT),
				 FIELD(last, DSI_RDBK_DATA_CTRL_COUNT), wait,
				 dsi_read(msm_host, REG_DSI_INTR_CTRL), READ_ONCE(msm_host->aa545_rx_irq),
				 dsi_read(msm_host, REG_DSI_LP_TIMER_CTRL));
			dev_info(&msm_host->pdev->dev,
				 "AA545 RX words %08x %08x %08x %08x -> %08x %08x %08x %08x ack=%08x phy=%08x timeout=%08x\\n",
				 reg[0], reg[1], reg[2], reg[3], dsi_read(msm_host, REG_DSI_RDBK_DATA(0)),
				 dsi_read(msm_host, REG_DSI_RDBK_DATA(1)), dsi_read(msm_host, REG_DSI_RDBK_DATA(2)),
				 dsi_read(msm_host, REG_DSI_RDBK_DATA(3)), dsi_read(msm_host, REG_DSI_ACK_ERR_STATUS),
				 dsi_read(msm_host, REG_DSI_DLN0_PHY_ERR), dsi_read(msm_host, REG_DSI_TIMEOUT_STATUS));
			if (!FIELD(last, DSI_RDBK_DATA_CTRL_COUNT))
				return 0;
		}
""" + anchor)

anchor = 'static int dsi_cmd_dma_add(struct msm_dsi_host *msm_host,'
assert source.count(anchor) == 1
source = source.replace(anchor, """
static bool aa545_status_read(struct msm_dsi_host *host,
			      const struct mipi_dsi_msg *msg)
{
	return !host->id && msg->channel == 0 &&
	       msg->type == MIPI_DSI_DCS_READ && msg->tx_len == 1 &&
	       msg->rx_len == 1 && msg->rx_buf &&
	       (*(const u8 *)msg->tx_buf == 0x0a ||
		*(const u8 *)msg->tx_buf == 0xb0);
}

""" + anchor)
a = source.index(anchor)
b = source.index('static int dsi_short_read1_resp', a)
dma = source[a:b]
dma = dma.replace('u8 *data;', 'u8 *data;\n\tbool batch_status = aa545_status_read(msm_host, msg);')
dma = dma.replace('if (len > msm_host->tx_size)', 'if (len + (batch_status ? 4 : 0) > msm_host->tx_size)')
dma = dma.replace('\t/* MSM specific command format in memory */', """
	if (batch_status) {
		/* VT3 queues this short write without LAST or BTA. */
		data[0] = 1;
		data[1] = 0;
		data[2] = MIPI_DSI_SET_MAXIMUM_RETURN_PACKET_SIZE;
		data[3] = 0;
		data += 4;
	}

	/* MSM specific command format in memory */""")
dma = dma.replace('\tif (cfg_hnd->ops->tx_buf_put)', """
	if (batch_status) {
		dev_info(&msm_host->pdev->dev, "AA545 batch descriptors %8ph\\n", data - 4);
		len += 4;
	}

	if (cfg_hnd->ops->tx_buf_put)""")
source = source[:a] + dma + source[b:]
a = source.index('\t\tret = dsi_cmds2buf_tx(msm_host, &max_pkt_size_msg);')
b = source.index('\n\n', a)
prefix = source[a:b]
source = source[:a] + '\t\tif (!aa545_status_read(msm_host, msg)) {\n' + '\n'.join('\t' + line for line in prefix.splitlines()) + '\n\t\t}' + source[b:]

anchor = '\t\tif (!aa545_status_read(msm_host, msg)) {'
assert source.count(anchor) == 1
source = source.replace(anchor, """
		if (aa545_status_read(msm_host, msg) && *(const u8 *)msg->tx_buf == 0x0a) {
			u32 lane_ctrl = dsi_read(msm_host, REG_DSI_LANE_CTRL);

			dev_info(&msm_host->pdev->dev,
				 "AA545 clock ctrl=%08x force_hs=%d status=%08x byte=%lu pixel=%lu esc=%lu\\n",
				 lane_ctrl, !!(lane_ctrl & DSI_LANE_CTRL_CLKLN_HS_FORCE_REQUEST),
				 dsi_read(msm_host, REG_DSI_LANE_STATUS),
				 clk_get_rate(msm_host->byte_clk),
				 clk_get_rate(msm_host->pixel_clk),
				 clk_get_rate(msm_host->esc_clk));
		}
""" + anchor)

anchor = "static unsigned long dsi_get_pclk_rate(const struct drm_display_mode *mode,"
assert source.count(anchor) == 1
source = source.replace(anchor, "static unsigned long dsi_get_pclk_rate(struct msm_dsi_host *host,\n\t\tconst struct drm_display_mode *mode,")
anchor = "\tunsigned long pclk_rate;\n\n\tpclk_rate = mode->clock * 1000u;"
assert source.count(anchor) == 1
source = source.replace(anchor, """
	unsigned long pclk_rate;
	u32 lane_rate;

	if (!is_bonded_dsi && !host->id && !host->cphy_mode && host->lanes == 4 &&
	    host->format == MIPI_DSI_FMT_RGB101010 && dsc &&
	    mode->hdisplay == 1440 && mode->vdisplay == 3168 && drm_mode_vrefresh(mode) == 60 &&
	    !of_property_read_u32(host->pdev->dev.of_node, "oplus,trial-dsi-lane-rate-hz",
				  &lane_rate) && lane_rate == 1363200000)
		return mult_frac((unsigned long)lane_rate, host->lanes, 30);

	pclk_rate = mode->clock * 1000u;""")
source = source.replace("dsi_get_pclk_rate(mode, msm_host->dsc", "dsi_get_pclk_rate(msm_host, mode, msm_host->dsc")
source = source.replace("dsi_get_pclk_rate(msm_host->mode, msm_host->dsc", "dsi_get_pclk_rate(msm_host, msm_host->mode, msm_host->dsc")
path.write_text(source)


anchor = '\tret = dsi_cmd_dma_tx(msm_host, len);'
assert source.count(anchor) == 1
source = source.replace(anchor, '''	if (aa545_status_read(msm_host, msg) &&
	    !(msg->flags & MIPI_DSI_MSG_USE_LPM) &&
	    *(const u8 *)msg->tx_buf == 0x0a &&
	    of_property_read_bool(msm_host->pdev->dev.of_node,
				  "oplus,trial-vt3-dsi-host")) {
		const u32 fifo_reg = REG_DSI_DMA_LEN + sizeof(u32);
		u32 fifo = dsi_read(msm_host, fifo_reg);
		u32 trig = dsi_read(msm_host, REG_DSI_TRIG_CTRL);
		u32 eot = dsi_read(msm_host, REG_DSI_EOT_PACKET_CTRL);

		dsi_write(msm_host, fifo_reg, 0x33);
		dsi_write(msm_host, REG_DSI_TRIG_CTRL,
			  trig & ~DSI_TRIG_CTRL_BLOCK_DMA_WITHIN_FRAME);
		dsi_write(msm_host, REG_DSI_EOT_PACKET_CTRL,
			  eot & ~DSI_EOT_PACKET_CTRL_TX_EOT_APPEND);
		dev_info(&msm_host->pdev->dev,
			 "AA545 VT3 TX len=%d ctrl=%08x dma=%08x fifo=%08x trigger=%08x lane=%08x lp=%08x eot=%08x clk=%08x\\n",
			 len, dsi_read(msm_host, REG_DSI_CTRL),
			 dsi_read(msm_host, REG_DSI_CMD_DMA_CTRL), dsi_read(msm_host, fifo_reg),
			 dsi_read(msm_host, REG_DSI_TRIG_CTRL), dsi_read(msm_host, REG_DSI_LANE_CTRL),
			 dsi_read(msm_host, REG_DSI_LP_TIMER_CTRL),
			 dsi_read(msm_host, REG_DSI_EOT_PACKET_CTRL), dsi_read(msm_host, REG_DSI_CLK_CTRL));
		ret = dsi_cmd_dma_tx(msm_host, len);
		dsi_write(msm_host, REG_DSI_EOT_PACKET_CTRL, eot);
		dsi_write(msm_host, REG_DSI_TRIG_CTRL, trig);
		dsi_write(msm_host, fifo_reg, fifo);
	} else {
		ret = dsi_cmd_dma_tx(msm_host, len);
	}''')
path.write_text(source)

source = source.replace('u32 aa545_rx_irq;', 'u32 aa545_rx_irq;\n\tbool aa545_direct_fifo_active;\n\tu32 aa545_saved_tpg;')
anchor = 'static int dsi_cmds2buf_tx('
assert source.count(anchor) == 1
source = source.replace(anchor, '''
/* DSI v2.8 TPG command FIFO registers relative to the shifted v6G base. */
#define AA545_DSI_FIFO_INIT 0x178
#define AA545_DSI_FIFO_RESET 0x1e8

static int aa545_cmd_direct_fifo(struct msm_dsi_host *host, int len)
{
	u32 tpg = dsi_read(host, REG_DSI_TEST_PATTERN_GEN_CTRL);
	unsigned long completed;

	u32 status = dsi_read(host, REG_DSI_STATUS0);

	dev_info(&host->pdev->dev, "AA545 direct FIFO starting control=%08x status=%08x\\n",
		 tpg, status);
	if (len != 8 || (status & DSI_STATUS0_CMD_MODE_DMA_BUSY))
		return -EBUSY;
	host->aa545_saved_tpg = tpg;

	/* Two embedded command descriptors for maximum return size and DCS 0x0a. */
	reinit_completion(&host->dma_comp);
	dsi_write(host, REG_DSI_TEST_PATTERN_GEN_CTRL, 0x00030006);
	dsi_write(host, AA545_DSI_FIFO_INIT, 0x00370001);
	dsi_write(host, AA545_DSI_FIFO_INIT, 0xa006000a);
	dsi_write(host, REG_DSI_DMA_LEN, len);
	wmb();
	host->aa545_direct_fifo_active = true;
	dsi_write(host, REG_DSI_TRIG_DMA, 1);
	completed = wait_for_completion_timeout(&host->dma_comp, msecs_to_jiffies(200));
	dev_info(&host->pdev->dev, "AA545 direct FIFO DMA completed=%d\\n", !!completed);
	return completed ? len : -ETIMEDOUT;
}

''' + anchor)
anchor = '\t\tret = dsi_cmd_dma_tx(msm_host, len);\n\t\tdsi_write(msm_host, REG_DSI_EOT_PACKET_CTRL, eot);'
assert source.count(anchor) == 1
source = source.replace(anchor, '''		ret = aa545_cmd_direct_fifo(msm_host, len);
		dsi_write(msm_host, REG_DSI_EOT_PACKET_CTRL, eot);''')
anchor = 'int msm_dsi_host_cmd_rx(struct mipi_dsi_host *host,'
assert source.count(anchor) == 1
source = source.replace(anchor, 'static int aa545_host_cmd_rx_inner(struct mipi_dsi_host *host,')
anchor = 'void msm_dsi_host_cmd_xfer_commit('
assert source.count(anchor) == 1
source = source.replace(anchor, '''int msm_dsi_host_cmd_rx(struct mipi_dsi_host *host, const struct mipi_dsi_msg *msg)
{
	struct msm_dsi_host *msm_host = to_msm_dsi_host(host);
	int ret = aa545_host_cmd_rx_inner(host, msg);

	if (msm_host->aa545_direct_fifo_active) {
		dsi_write(msm_host, REG_DSI_TEST_PATTERN_GEN_CTRL, 0);
		dsi_write(msm_host, AA545_DSI_FIFO_RESET, 1);
		udelay(1);
		dsi_write(msm_host, AA545_DSI_FIFO_RESET, 0);
		dsi_write(msm_host, REG_DSI_TEST_PATTERN_GEN_CTRL, msm_host->aa545_saved_tpg);
		msm_host->aa545_direct_fifo_active = false;
	}
	return ret;
}

''' + anchor)
path.write_text(source)

source = source.replace('#include <linux/iopoll.h>', '#include <linux/iopoll.h>\n#include <linux/unaligned.h>')
anchor = 'u32 aa545_saved_tpg;'
source = source.replace(anchor, anchor + '\n\tu8 aa545_fifo_cmd[64];')
anchor = '\tif (cfg_hnd->ops->tx_buf_put)'
first = source.index(anchor, source.index('static int dsi_cmd_dma_add'))
source = source[:first] + '''	if (len <= 60 &&
	    of_property_read_bool(msm_host->pdev->dev.of_node, "oplus,trial-vt3-dsi-host"))
		memcpy(msm_host->aa545_fifo_cmd, data - (batch_status ? 4 : 0), len);

''' + source[first:]
a = source.index('\tif (len != 8 || (status & DSI_STATUS0_CMD_MODE_DMA_BUSY))')
b = source.index('\tdsi_write(host, REG_DSI_DMA_LEN, len);', a)
source = source[:a] + '''	if (len > 60 || (len & 3) || (status & DSI_STATUS0_CMD_MODE_DMA_BUSY))
		return -EBUSY;
	host->aa545_saved_tpg = tpg;

	reinit_completion(&host->dma_comp);
	dsi_write(host, REG_DSI_TEST_PATTERN_GEN_CTRL, 0x00030006);
	for (int i = 0; i < len; i += sizeof(u32))
		dsi_write(host, AA545_DSI_FIFO_INIT,
			  get_unaligned_le32(host->aa545_fifo_cmd + i));
	if (len & sizeof(u32))
		dsi_write(host, AA545_DSI_FIFO_INIT, 0);
''' + source[b:]
a = source.index('\tif (aa545_status_read(msm_host, msg) &&\n\t    !(msg->flags')
b = source.index('\n\tif (ret < 0) {', a)
source = source[:a] + '''	if (of_property_read_bool(msm_host->pdev->dev.of_node, "oplus,trial-vt3-dsi-host")) {
		if (len <= 60) {
			ret = aa545_cmd_direct_fifo(msm_host, len);
			if (!msg->rx_len && msm_host->aa545_direct_fifo_active) {
				dsi_write(msm_host, REG_DSI_TEST_PATTERN_GEN_CTRL, 0);
				dsi_write(msm_host, AA545_DSI_FIFO_RESET, 1);
				udelay(1);
				dsi_write(msm_host, AA545_DSI_FIFO_RESET, 0);
				dsi_write(msm_host, REG_DSI_TEST_PATTERN_GEN_CTRL, msm_host->aa545_saved_tpg);
				msm_host->aa545_direct_fifo_active = false;
			}
		} else {
			const u32 vbif_reg = 0x1c8;
			const u32 fifo_reg = REG_DSI_DMA_LEN + sizeof(u32);

			dsi_write(msm_host, vbif_reg, dsi_read(msm_host, vbif_reg) | 7);
			dsi_write(msm_host, fifo_reg, 0x33);
			wmb();
			dev_info(&msm_host->pdev->dev, "AA545 long DMA len=%d vbif=%08x\\n",
				 len, dsi_read(msm_host, vbif_reg));
			ret = dsi_cmd_dma_tx(msm_host, len);
		}
	} else {
		ret = dsi_cmd_dma_tx(msm_host, len);
	}''' + source[b:]
anchor = 'data |= DSI_TRIG_CTRL_BLOCK_DMA_WITHIN_FRAME;'
assert source.count(anchor) == 1
source = source.replace(anchor, anchor + '''
	if (of_property_read_bool(msm_host->pdev->dev.of_node, "oplus,trial-vt3-dsi-host"))
		data &= ~DSI_TRIG_CTRL_BLOCK_DMA_WITHIN_FRAME;''')
path.write_text(source)
