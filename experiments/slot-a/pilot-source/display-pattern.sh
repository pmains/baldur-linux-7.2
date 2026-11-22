#!/bin/busybox sh
bb() { /bin/busybox "$@"; }
exec > /run/aa545-vt.log 2>&1
for n in $(bb seq 1 30); do
    if [ -c /dev/tty1 ] && [ "$(bb cat /sys/class/graphics/fb0/name 2>/dev/null)" = msm-kmsdrmfb ]; then
        break
    fi
    bb sleep 1
done
[ -c /dev/tty1 ] && [ "$(bb cat /sys/class/graphics/fb0/name 2>/dev/null)" = msm-kmsdrmfb ] || exit 1
bb chvt 1 || exit 1
bb dmesg -n 1
boot_id=$(bb cat /proc/sys/kernel/random/boot_id) || exit 1
{
    printf '\033c\033[?25l\033[9;0]'
    printf '\033]P00c1118\033]P4172a3b\033]P665e2b0\033]P78ca7b8'
    printf '\033[37;40m\033[2J\033[H'
    printf '\033[36;44m\033[2K\033[2;1H\033[2K\033[3;1H\033[2K'
    printf '\033[2;3HBaldur Linux 7.2'
    printf '\033[37;40m\033[6;3HBoot ID\033[7;3H%s' "$boot_id"
} > /dev/tty1 || exit 1
echo AA545_VT1_BANNER_SHOWN >/dev/kmsg
