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

## Scope

The tagged release notes identify the exact on-device results for this preview. Other Baldur trials cover different images. This preview uses firmware-supplied display state only where the bootloader leaves it available, and makes no display, GPU, or HTP workload claim. Use USB ACM and USB Ethernet to observe the trial.
