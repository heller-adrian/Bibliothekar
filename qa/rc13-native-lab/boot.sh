#!/bin/busybox sh
set -eu
/bin/busybox --install -s /bin
trap 'echo "RC13_BOOT_FAILED"; poweroff -f' EXIT
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
modprobe virtio_pci
modprobe virtio_blk
modprobe crc32c_generic
modprobe ext4
for second in 1 2 3 4 5 6 7 8 9 10; do
    test ! -b /dev/vda || break
    sleep 1
done
mount -t ext4 /dev/vda /newroot
umount /sys
umount /proc
mount --move /dev /newroot/dev
exec switch_root /newroot /rc13-native-init
