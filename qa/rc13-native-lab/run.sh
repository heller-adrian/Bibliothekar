#!/bin/bash
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_ENVIRONMENT:-} == github-hosted && ${RUNNER_OS:-} == Linux ]]
[[ ${GITHUB_REPOSITORY:-} == heller-adrian/Bibliothekar ]]
[[ $(git -C product rev-parse HEAD) == "$QUALIFIED_SOURCE" ]]
lab=$(realpath lab/qa/rc13-native-lab)
scratch=$(mktemp -d "$RUNNER_TEMP/rc13-native.XXXXXXXX")
evidence="$RUNNER_TEMP/rc13-native-evidence"
mkdir "$evidence"
trap 'sudo rm -rf -- "$scratch"' EXIT
fs="$scratch/guest"
mkdir "$scratch/debs"
printf 'product=%s\nrunner=%s\n' "$QUALIFIED_SOURCE" "$GITHUB_SHA" > "$evidence/source.txt"
sudo apt-get update -qq
sudo apt-get install -y -q --no-install-recommends debootstrap qemu-system-x86
sudo debootstrap --variant=minbase --include=initramfs-tools,linux-base,kmod,iproute2,ca-certificates,python3-venv,libimage-exiftool-perl,libssl3t64,libtirpc3t64,libblkid1,libuuid1,libudev1,liblz4-1,libzstd1,zlib1g,zstd,busybox     trixie "$fs" https://deb.debian.org/debian > "$evidence/guest-install.log" 2>&1

base=https://download.truenas.com/TrueNAS-SCALE-Goldeye/25.10.0/packages
python3 - "$base" "$scratch/debs" <<'PY'
from gzip import decompress
from hashlib import sha256
from pathlib import Path
import sys
from urllib.parse import quote
from urllib.request import urlopen

base, directory = sys.argv[1:]
with urlopen(base + '/Packages.gz', timeout=30) as response:
    index = response.read()
assert sha256(index).hexdigest() == '9f8553bd1f4adbc123dade0596055b2b58dc99a1230dffd6f70dcc08f34a48ed'
wanted = {'linux-image-truenas-production-amd64', 'openzfs-zfs-modules-6.12.33-production+truenas',
          'openzfs-zfsutils', 'openzfs-libnvpair3', 'openzfs-libuutil3',
          'openzfs-libzfs6', 'openzfs-libzfsbootenv1', 'openzfs-libzpool6'}
for entry in decompress(index).decode().split('\n\n'):
    fields = dict(row.split(': ', 1) for row in entry.splitlines() if row and not row[0].isspace() and ': ' in row)
    name = fields.get('Package')
    if name not in wanted:
        continue
    filename = Path(fields['Filename']).name
    with urlopen(base + '/' + quote(filename), timeout=90) as response:
        content = response.read()
    assert sha256(content).hexdigest() == fields['SHA256']
    (Path(directory) / filename).write_bytes(content)
    wanted.remove(name)
assert not wanted, wanted
PY
for package in "$scratch"/debs/*.deb; do
    sudo dpkg-deb -x "$package" "$fs"
done
kernel=6.12.33-production+truenas
sudo chroot "$fs" depmod "$kernel"
sudo chroot "$fs" ldconfig
printf 'virtio_pci\nvirtio_blk\next4\n' | sudo tee -a "$fs/etc/initramfs-tools/modules" >/dev/null
sudo unshare --mount --propagation private bash -euc '
    mount -t proc proc "$1/proc"
    mount -t sysfs sysfs "$1/sys"
    chroot "$1" update-initramfs -v -c -k "$2"
' _ "$fs" "$kernel" >> "$evidence/guest-install.log" 2>&1
sudo install -m 755 "$lab/guest.sh" "$fs/rc13-native-init"
sudo mkdir -p "$fs/opt/bibliothekar"
git -C product archive "$QUALIFIED_SOURCE" | sudo tar -xf - -C "$fs/opt/bibliothekar"
sudo chroot "$fs" useradd --system --uid 568 --user-group --home-dir /var/lib/rc13-lab --create-home rc13lab
sudo chroot "$fs" python3 -m venv /opt/rc13-venv
sudo chroot "$fs" /opt/rc13-venv/bin/python -m pip --disable-pip-version-check install --no-cache-dir     -r /opt/bibliothekar/requirements.txt -c /opt/bibliothekar/requirements-rc.constraints.txt     pytest httpx tinycss2 >> "$evidence/guest-install.log" 2>&1

disk="$scratch/root.ext4"
truncate -s 4G "$disk"
sudo mkfs.ext4 -q -F -d "$fs" "$disk"
sudo chown "$(id -u):$(id -g)" "$disk"
vdev="$scratch/pool.img"
truncate -s 3G "$vdev"
accelerator=(-accel tcg -cpu max)
if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
    accelerator=(-accel kvm -cpu host)
fi
timeout 15m qemu-system-x86_64 "${accelerator[@]}" -smp 2 -m 4096 -nographic -no-reboot -nic none     -kernel "$fs/boot/vmlinuz-$kernel" -initrd "$fs/boot/initrd.img-$kernel"     -append "root=/dev/vda rw console=ttyS0 init=/rc13-native-init panic=1"     -drive "file=$disk,format=raw,if=virtio" -drive "file=$vdev,format=raw,if=virtio"     2>&1 | tee "$evidence/console.log"
grep -Eq '^RC13_NATIVE_EXIT=0[[:space:]]*$' "$evidence/console.log"
