# Local build inputs

Use an external directory that is outside the checkout. Put the pinned Linux archive from kernel.org at `linux-7.2.15.tar.xz` and check it against `config/upstream.sha256`. Stage each initramfs input at the exact relative path shown in `config/local-inputs.sha256`. The build checks hashes before extracting the kernel or packaging an image.

- `bin/busybox` is the ARM64 musl-linked BusyBox from the tested VT3 setup. `lib/ld-musl-aarch64.so.1` is its matching musl loader. Use your existing local copies with the listed hashes. Preserve their source and license obligations if distributing those binaries separately.
- Use only firmware obtained from your own device or a source with appropriate permissions. For a provisioned VT3 device, obtain the ADSP and CDSP MDT and all listed split segments from the firmware filesystem while it is mounted read-only. The Wi-Fi files belong under `lib/firmware/ath12k/WCN7850/hw2.0/`. The input list gives the full expected set. Board data should be appropriate for your hardware.
- The pre-existing VT3 rootfs supplies SSH userspace and its local access configuration on the phone. The build does not read a host SSH key or copy a rootfs into the image.

The repository ships source, input hashes, and build instructions. Firmware, the loader, BusyBox, and generated images are supplied locally.
