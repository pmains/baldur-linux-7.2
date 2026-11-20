# Device and recovery

Test target is OnePlus 12 CPH2583, waffle, with an unlocked bootloader and the known-good VT3 6.1 installation already provisioned. The RAM init assumes the VT3 ext4 root is `/dev/sda14`. Confirm partition identity and the current recovery path for your device before attempting a boot. This is neither an Android installation guide nor a persistent boot image.

Use the tested USB-A to USB-C host connection. Start host capture and confirm VT3 is healthy. Confirm Fastboot identifies the device as `pineapple`, confirm the expected active slot, and check the reported download limit. Use `fastboot boot /path/to/baldur-7.2.15-preview-01.ram.img` once. This runs the trial from RAM. Keep an on-device observer available. The image uses a timed session and can end the trial through the RAM-backed `/run/poweroff` control over the authenticated USB SSH connection.

On the existing VT3 setup, the test image exposes CDC ACM and USB Ethernet. The root filesystem is mounted with `ro,noload` and its block device is set read-only. The SSH service uses the provisioned VT3 configuration. Verify the running kernel identity and read-only guard before exercising a feature.

If runtime USB is lost, wait for the session timeout. If the phone is hung, use the established hardware restart, Power and Volume Up, and allow VT3 to boot. Confirm the expected VT3 release and a new boot ID over USB SSH before continuing. Avoid using the image for flash or repartition operations.
