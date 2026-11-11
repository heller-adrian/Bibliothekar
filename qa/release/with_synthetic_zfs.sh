#!/usr/bin/env bash
set -euo pipefail

if [[ ${GITHUB_ACTIONS:-} != true || ${RUNNER_ENVIRONMENT:-} != github-hosted || ${RUNNER_OS:-} != Linux ]]; then
  echo 'Synthetic ZFS qualification requires a disposable GitHub-hosted Linux runner.' >&2
  exit 1
fi

if ! command -v zpool >/dev/null || ! modinfo zfs >/dev/null 2>&1; then
  packages=(zfsutils-linux)
  if ! modinfo zfs >/dev/null 2>&1; then
    packages+=("linux-modules-extra-$(uname -r)")
  fi
  bash "$(dirname -- "${BASH_SOURCE[0]}")/install_runner_packages.sh" "${packages[@]}"
fi
sudo modprobe zfs
test -c /dev/zfs

scratch="$(mktemp -d "${RUNNER_TEMP:?}/adoption-zfs.XXXXXXXX")"
pool="bibliothekar_qa_${scratch##*.}"
created=false
cleanup() {
  if [[ "$created" == true ]]; then
    sudo zpool destroy "$pool"
  fi
  rm -rf -- "$scratch"
}
trap cleanup EXIT
truncate -s 512M "$scratch/vdev"
sudo zpool create -o cachefile=none -m none "$pool" "$scratch/vdev"
created=true
sudo zfs create -o mountpoint="$scratch/media" "$pool/media"
sudo zfs create -o mountpoint="$scratch/other" "$pool/other"
sudo chown "$(id -u):$(id -g)" "$scratch/media" "$scratch/other"
sudo zfs list -H -o name,mountpoint "$pool/media" "$pool/other"
export ADOPTION_ZFS_ROOT="$scratch/media"
export ADOPTION_ZFS_OTHER="$scratch/other"
"$@"
