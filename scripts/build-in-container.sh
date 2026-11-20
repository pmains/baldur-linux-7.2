#!/bin/bash
set -euo pipefail
export ARCH=arm64 LLVM=1 LC_ALL=C TZ=UTC
export KBUILD_BUILD_USER=baldur KBUILD_BUILD_HOST=local KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='Sun Nov 1 12:44:00 UTC 2026'
cd /inputs
sha256sum -c /release/config/upstream.sha256
sha256sum -c /release/config/local-inputs.sha256
clang --version | head -1 | grep -F '18.1.3'
mkdir -p /build/wifi-01
tar -xJf linux-7.2.15.tar.xz -C /build
src=/build/linux-7.2.15
out=/build/wifi-01
for patch in /release/patches/*.patch; do git -C "$src" apply "$patch"; done
cp /release/config/baldur.config "$out/.config"
"$src/scripts/config" --file "$out/.config" --set-str INITRAMFS_SOURCE /release/board/initramfs.list
make -C "$src" O="$out" olddefconfig
make -C "$src" O="$out" -j"${JOBS:-6}" scripts_dtc
"$out/scripts/dtc/dtc" -q -I dts -O dtb -o "$out/baldur.dtb" /release/board/waffle.dts
make -C "$src" O="$out" -j"${JOBS:-6}" Image
cp "$out/arch/arm64/boot/Image" "$out/Image"
llvm-objcopy --dump-section ".notes=$out/kernel.notes" "$out/vmlinux" "$out/vmlinux.notes-copy"
python3 /release/scripts/patch-dwc3.py "$out/Image" "$out/vmlinux" "$out/System.map" "$out/Image.patched"
python3 /release/scripts/package.py "$out" /artifacts "$SOURCE_COMMIT"
cp "$out/baldur.dtb" "$out/.config" "$out/patch-report.json" /artifacts/
