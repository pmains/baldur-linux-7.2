# Baldur Linux 7.2 Developer Preview 01

A source-first RAM-boot preview for the unlocked OnePlus 12 CPH2583 (waffle, SM8650). It assumes a working VT3 installation and a provisioned read-only Linux root. See [device and recovery notes](docs/device.md) before using Fastboot.

The pinned base is [Linux 7.2.15](https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.2.15.tar.xz). The kernel patches, exact config, board DTS, initramfs source, and Android v4 packaging implementation are in this checkout.

## Build

Use a Linux arm64 Docker environment with at least 10 GB free. Prepare the local inputs following [the staging guide](docs/local-inputs.md). Use Ubuntu Clang and LLVM 18.1.3, the versions used for the reference trial. The baseline build does not use Rust. Build the toolchain container, then build from a clean checkout.

```sh
docker build --platform linux/arm64 -t baldur-toolchain:llvm18 .
TOOLCHAIN_IMAGE=baldur-toolchain:llvm18 scripts/build.sh /path/to/local-inputs /path/to/output
```

The build verifies every local input hash, disables container networking, and emits a RAM image and a receipt with its SHA-256 and source commit. Run the same commands twice in fresh checkouts with the same toolchain and inputs to compare checksums.

## Feature status

The **Verified** column records what ran together on one OnePlus 12 in the [Developer Preview 01 RAM trial](https://github.com/pmains/baldur-linux-7.2/releases/tag/v7.2.15-preview.1). Use the release tag to reproduce the tested image.

| Component | Verified on Preview 01 | Still to validate or bring up |
| --- | --- | --- |
| Boot and recovery | Fastboot RAM boot and return to VT3 Linux 6.1 | Persistent boot and automatic fallback |
| USB | CDC ACM logs and USB Ethernet with authenticated SSH | Cable reconnect on this exact image, USB-C role switching, and USB resume |
| Internal storage | UFS enumeration and a read-only ext4 root | Writable root, recovery behavior, and UFS suspend/resume |
| Wi-Fi | Qualcomm WCN7850 initialized via ath12k and registered a wireless PHY | Access-point association, data transfer, 802.11be link negotiation, and reconnect/resume |
| Charging and battery | Battery manager reported USB charging status and battery telemetry | USB-C charging and fast charging |
| PMIC ADC | Four channels read successfully: reference voltage, PMK8550 die temperature, system rail voltage, and battery voltage. Twelve reads produced twelve conversion interrupts. | Board thermistor readings and ADC threshold monitoring |
| CPU thermal control | All four CPU policies throttled and recovered when their passive trips were temporarily lowered. A guarded 60-second CPU load test passed. | Longer workloads, battery and skin thermal limits, and GPU cooling |
| Qualcomm DSPs and NPU | ADSP and CDSP booted, GLINK channels appeared, and the CDSP answered a FastRPC capability query | HTP inference and DSP workloads |
| Display and GPU | | Visible console on this exact image, native DSI panel initialization, and an Adreno rendering or compute workload |
| Other handset I/O | | Bluetooth, cellular data (MPSS), GNSS, touch, audio, NFC, camera, sensors, haptics, and fingerprint |
| System power management | | End-to-end suspend/resume |

Related trials used different RAM images. Those trials demonstrated a readable tty1 banner through the firmware display handoff, a USB cable reconnect with both ACM and SSH recovery, and an Adreno chip-ID read. The preview matrix counts only the checks repeated on the tagged image.

## Later combined pilot

[Combined image and slot A bring-up](docs/pilot-bringup.md) records the subsequent RAM-boot and inference results, the verified header workaround, and the remaining installed-boot blocker. The corresponding experimental source and probe code are under `experiments/`.
