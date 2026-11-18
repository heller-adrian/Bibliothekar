#!/usr/bin/env bash
set -euo pipefail

image="$1"
revision="$2"
scratch="$(mktemp -d "${RUNNER_TEMP:?}/legacy-adoption-smoke.XXXXXXXX")"
media="${ADOPTION_ZFS_ROOT:?Use the synthetic ZFS runner}"
container=""
cleanup() {
  if [[ -n "$container" ]]; then
    docker logs "$container" >&2 || true
    docker rm -f "$container" >/dev/null || true
  fi
  sudo rm -rf -- "$scratch"
}
trap cleanup EXIT

case "$image" in
  *'@sha256:'*) docker pull "$image" ;;
  "bibliothekar-qa:$revision") ;; # Local image built by the synthetic QA job.
  *) echo "Expected a qualified digest or the exact local QA image." >&2; exit 1 ;;
esac
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$revision"
export ADOPTION_SMOKE_VERSION="$(python -c 'from app import __version__; print(__version__)')"
export ADOPTION_SMOKE_PASSWORD=synthetic-legacy-adoption-smoke-password
methods=(manual script rollback skip review)
previous_image="${3:-}"
if [[ -n "$previous_image" ]]; then
  [[ "$previous_image" =~ ^ghcr\.io/heller-adrian/bibliothekar@sha256:[0-9a-f]{64}$ ]]
  stable_100="ghcr.io/heller-adrian/bibliothekar@sha256:5a1d1053d39d011a4236735cf51ad7e70a35b369a981c63b99b3c82c1f4240fb"
  docker pull "$stable_100"
  docker pull "$previous_image"
  methods+=(upgrade-rc22 upgrade-100)
fi

start_container() {
  docker run -d --read-only --tmpfs /tmp:size=64m,mode=1777 --security-opt no-new-privileges \
    -p 127.0.0.1::8080 \
    --mount "type=bind,source=$install_root/appdata,target=/appdata" \
    --mount "type=bind,source=$workspace,target=/workspace" \
    --mount "type=bind,source=$archive,target=/main-library,readonly" \
    --mount "type=bind,source=$source,target=/sources/nas,readonly" \
    -e "BIBLIOTHEKAR_ADMIN_PASSWORD=$ADOPTION_SMOKE_PASSWORD" \
    -e KAMERA_APPDATA=/appdata -e KAMERA_WORKSPACE=/workspace \
    -e KAMERA_POOL_PROBE=/workspace -e KAMERA_ARCHIVE_ROOT=/main-library \
    -e KAMERA_NAS_SOURCE_ROOT=/sources/nas "$1"
}

for method in "${methods[@]}"; do
  install_root="$scratch/$method"
  archive="$media/archive-$method"
  source="$media/source-$method"
  mkdir -m 755 "$archive" "$source"
  workspace="$install_root/workspace"
  if [[ "$method" == review ]]; then
    # Use the second synthetic dataset for the writable Workspace. Source
    # and archive still share the original, independently read-only dataset.
    acl_media="${ADOPTION_ZFS_OTHER:?Use the synthetic ZFS runner}"
    acl_dataset="$(findmnt -n -o SOURCE --mountpoint "$acl_media")"
    [[ "$acl_dataset" == bibliothekar_qa_*/other ]]
    sudo zfs set acltype=posix xattr=sa "$acl_dataset"
    workspace="$acl_media/workspace-review"
  fi
  sudo install -d -m 0750 -o 568 -g 568 "$install_root/appdata" "$workspace"
  if [[ "$method" == review ]]; then
    sudo setfacl -m u:65534:rx,d:u:65534:rwx,d:m::rwx "$workspace"
    printf 'native ZFS review RAW\n' > "$source/undated.raf"
    printf 'native ZFS review JPEG\n' > "$source/undated.jpg"
    printf 'native ZFS review sidecar\n' > "$source/undated.raf.xmp"
  elif [[ "$method" != skip && "$method" != upgrade-100 ]]; then
    if [[ "$method" == manual ]]; then day=21; else day=22; fi
    directory="$source/first/old-folders/camera/import"
    mkdir -p "$directory"
    printf 'synthetic raw for %s\n' "$method" > "$directory/sample.raf"
    cat > "$directory/sample.xmp" <<XML
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:CreateDate="2026-07-${day}T12:34:56+02:00"/>
  </rdf:RDF>
</x:xmpmeta>
XML
  fi
  initial_image="$image"
  case "$method" in
    upgrade-rc22) initial_image="$previous_image" ;;
    upgrade-100) initial_image="$stable_100" ;;
  esac
  container="$(start_container "$initial_image")"
  test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/main-library"}}{{.RW}}{{end}}{{end}}' "$container")" = false
  test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/sources/nas"}}{{.RW}}{{end}}{{end}}' "$container")" = false
  if [[ "$method" == upgrade-rc22 ]]; then
    ADOPTION_SMOKE_VERSION=1.0.1 python qa/release/smoke_legacy_adoption.py "$container" "$source" "$archive" "$install_root/appdata" script
    find "$archive" -type f -print0 | sort -z | xargs -0 sha256sum > "$scratch/upgrade-archive.sha256"
    test -s "$scratch/upgrade-archive.sha256"
    docker stop "$container" >/dev/null
    docker rm "$container" >/dev/null
    container="$(start_container "$image")"
    python qa/release/smoke_legacy_adoption.py "$container" "$source" "$archive" "$install_root/appdata" upgrade
    sha256sum --check "$scratch/upgrade-archive.sha256"
    echo "Upgrade from RC22 retained the registered archive, receipt and SHA-256 on native ZFS."
  elif [[ "$method" == upgrade-100 ]]; then
    ADOPTION_SMOKE_VERSION=1.0.0 python qa/release/smoke_legacy_adoption.py "$container" "$source" "$archive" "$install_root/appdata" prepare-upgrade-100
    docker stop "$container" >/dev/null
    docker rm "$container" >/dev/null
    container="$(start_container "$image")"
    python qa/release/smoke_legacy_adoption.py "$container" "$source" "$archive" "$install_root/appdata" upgrade-100
  else
    python qa/release/smoke_legacy_adoption.py "$container" "$source" "$archive" "$install_root/appdata" "$method"
  fi
  if [[ "$method" == review ]]; then
    stage="$(sudo find "$workspace" -type d -name .bibliothekar-legacy-review-stage -print -quit)"
    test -n "$stage"
    test "$(sudo stat -c %a "$stage")" = 700
    # Prove the inherited named principal can reach the parent first.
    stage_container="/workspace${stage#"$workspace"}"
    docker exec --user 65534:65534 "$container" test -x "$(dirname "$stage_container")"
    if docker exec --user 65534:65534 "$container" test -x "$stage_container"; then
      echo "A non-owner could traverse the private working directory." >&2
      exit 1
    fi
    echo "Native ZFS POSIX ACL inheritance preserved private review staging."
  fi
  docker rm -f "$container" >/dev/null
  container=""
done
