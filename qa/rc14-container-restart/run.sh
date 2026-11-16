#!/usr/bin/env bash
set -euo pipefail
image="$1"
revision="$2"
scratch="$(mktemp -d "${RUNNER_TEMP:?}/rc14-restart.XXXXXXXX")"
media="${ADOPTION_ZFS_ROOT:?}"
writable="${ADOPTION_ZFS_OTHER:?}"
container=
cleanup() {
    if [[ -n "$container" ]]; then
        docker logs --tail 100 "$container" >&2 || true
        docker rm -f "$container" >/dev/null || true
    fi
    sudo rm -rf -- "$scratch"
}
trap cleanup EXIT

docker pull "$image"
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$revision"
source="$media/rc14-cancel-source"
archive="$media/rc14-cancel-target"
workspace="$writable/rc14-cancel-workspace"
mkdir -m 755 "$source" "$archive"
sudo install -d -m 0750 -o 568 -g 568 "$scratch/appdata" "$workspace"
printf 'review first\n' > "$source/a-before.jpg"
printf 'review raw\n' > "$source/undated.raf"
printf 'review jpeg\n' > "$source/undated.jpg"
printf 'review sidecar\n' > "$source/undated.raf.xmp"
if ! command -v ffmpeg >/dev/null; then
    bash qa/release/install_runner_packages.sh ffmpeg
fi
ffmpeg -hide_banner -loglevel error -f lavfi -i color=black:s=16x16:r=1 -t 1 -c:v mpeg4 -map_metadata -1 "$source/z-video.mp4"
python3 - "$source/z-video.mp4" <<'PY'
from pathlib import Path
import struct,sys
p=Path(sys.argv[1])
size=160*1024*1024
with p.open('ab') as mp4:
    mp4.write(struct.pack('!I4s',size,b'free'))
    mp4.truncate(mp4.tell()+size-8)
PY
export ADOPTION_SMOKE_PASSWORD=synthetic-legacy-adoption-restart-password
container="$(docker run -d --read-only --tmpfs /tmp:size=64m,mode=1777 --security-opt no-new-privileges --cpus=.1 \
    -p 127.0.0.1::8080 \
    --mount "type=bind,source=$scratch/appdata,target=/appdata" \
    --mount "type=bind,source=$workspace,target=/workspace" \
    --mount "type=bind,source=$archive,target=/main-library,readonly" \
    --mount "type=bind,source=$source,target=/sources/nas,readonly" \
    -e "BIBLIOTHEKAR_ADMIN_PASSWORD=$ADOPTION_SMOKE_PASSWORD" \
    -e KAMERA_APPDATA=/appdata -e KAMERA_WORKSPACE=/workspace \
    -e KAMERA_POOL_PROBE=/workspace -e KAMERA_ARCHIVE_ROOT=/main-library \
    -e KAMERA_NAS_SOURCE_ROOT=/sources/nas "$image")"
for mount in /main-library /sources/nas; do
    test "$(docker inspect --format "{{range .Mounts}}{{if eq .Destination \"$mount\"}}{{.RW}}{{end}}{{end}}" "$container")" = false
done
# Reuse the tested authentication and request helpers with a synthetic review scenario.
python3 - "$container" "$source" "$archive" "$scratch/appdata" <<'PY'
import sys
from pathlib import Path
original=Path('qa/release/smoke_legacy_adoption.py').read_text()
anchor='    if method == "review":\n'
assert original.count(anchor)==1
scenario=Path('qa/rc14-container-restart/scenario.py').read_text()
script=original.replace(anchor,scenario+'\n'+anchor)
module={'__name__':'__rc14_restart__'}
exec(compile(script,'rc14-container-restart.py','exec'),module)
module['smoke'](sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),'review-cancel')
PY
