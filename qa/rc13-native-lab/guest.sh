#!/bin/bash
set -Eeuo pipefail
finish() {
    local result=$?
    trap - EXIT
    printf '\nRC13_NATIVE_EXIT=%s\n' "$result"
    sync
    busybox poweroff -f
}
trap finish EXIT
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mountpoint -q /proc || mount -t proc proc /proc
mountpoint -q /sys || mount -t sysfs sysfs /sys
mountpoint -q /dev || mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts
mountpoint -q /dev/pts || mount -t devpts devpts /dev/pts
test -b /dev/vdb
uname -r
modprobe zfs
zfs version
zpool create -o cachefile=none -m none rc13qa /dev/vdb
zfs create -o mountpoint=/mnt/rc13-workspace -o acltype=nfsv4 -o aclmode=restricted -o aclinherit=passthrough rc13qa/workspace
zfs create -o mountpoint=/mnt/rc13-media rc13qa/media
zfs get acltype,aclmode,aclinherit rc13qa/workspace
install -d -m 755 /opt/rc13-lab/bin
zfs get -Hp -o value acltype,aclmode,aclinherit rc13qa/workspace > /opt/rc13-lab/workspace-properties
test "$(cat /opt/rc13-lab/workspace-properties)" = "$(printf '%s\n' nfsv4 restricted passthrough)"
chmod 444 /opt/rc13-lab/workspace-properties
# Only the fixture's exact getter reads the root-recorded dataset properties.
# All writes and filesystem operations remain in the unprivileged process.
cat > /opt/rc13-lab/bin/zfs <<'EOF'
#!/bin/sh
if [ "$#" = 6 ] && [ "$*" = 'get -Hp -o value acltype,aclmode,aclinherit rc13qa/workspace' ]; then
    exec cat /opt/rc13-lab/workspace-properties
fi
exec /usr/sbin/zfs "$@"
EOF
chmod 755 /opt/rc13-lab/bin/zfs
install -d -o rc13lab -g rc13lab /var/lib/rc13-lab/tmp
chown rc13lab:rc13lab /mnt/rc13-workspace /mnt/rc13-media
cd /opt/bibliothekar
runuser -u rc13lab -- env PATH=/opt/rc13-lab/bin:/opt/rc13-venv/bin:$PATH PYTHONPATH=/opt/bibliothekar PYTHONDONTWRITEBYTECODE=1     TMPDIR=/var/lib/rc13-lab/tmp ADOPTION_NFSV4_ROOT=/mnt/rc13-workspace ADOPTION_ZFS_ROOT=/mnt/rc13-media     KAMERA_WORKSPACE=/var/lib/rc13-lab/workspace KAMERA_ARCHIVE_ROOT=/var/lib/rc13-lab/archive     KAMERA_DATABASE_DIR=/var/lib/rc13-lab/db     /opt/rc13-venv/bin/python -m pytest -q -p no:cacheprovider --tb=short     'tests/backend/test_legacy_adoption_integration.py::test_review_batch_resumes_after_interruption_and_reintegrates_corrected_copy[review-unlinked]'     'tests/backend/test_legacy_adoption_integration.py::test_review_metadata_stages_distinct_times_and_adopts_into_existing_draft[metadata-zfs]'
zpool destroy rc13qa
