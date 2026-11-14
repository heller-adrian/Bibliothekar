#!/usr/bin/env bash
set -euo pipefail

if [[ ${GITHUB_ACTIONS:-} != true || ${RUNNER_ENVIRONMENT:-} != github-hosted || ${RUNNER_OS:-} != Linux ]]; then
  echo 'QA packages require a disposable GitHub-hosted Linux runner.' >&2
  exit 1
fi
source /etc/os-release
test "${ID:-}" = ubuntu
test "${VERSION_CODENAME:-}" = noble
test "$#" -gt 0

scratch="$(mktemp -d "${RUNNER_TEMP:?}/ubuntu-apt.XXXXXXXX")"
trap 'rm -rf -- "$scratch"' EXIT
sources="$scratch/ubuntu.sources"
# Keep the runner's sources and DNS unchanged. Only these APT invocations use
# the mirrors below. APT verifies all indexes and packages with Ubuntu's keyring.
apt_options=(
  -o "Dir::Etc::sourcelist=$sources"
  -o Dir::Etc::sourceparts=-
  -o APT::Update::Error-Mode=any
  -o Acquire::Retries=0
  -o Acquire::https::Timeout=15
)

# The Azure and Canonical archive names have both failed to resolve on runners.
# Try independent mirrors of all required suites, including noble-security.
for mirror in \
  'https://mirrors.edge.kernel.org/ubuntu/' \
  'https://mirror.math.princeton.edu/pub/ubuntu/' \
  'https://archive.ubuntu.com/ubuntu/'; do
  echo "Fetching Ubuntu QA packages from $mirror"
  cat > "$sources" <<EOF
Types: deb
URIs: $mirror
Suites: noble noble-updates noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
  # Separate fetching from installation so a mirror failure never causes a
  # second install attempt after dpkg has begun changing the runner.
  if timeout 75s sudo apt-get "${apt_options[@]}" update -qq &&
     timeout 120s sudo apt-get "${apt_options[@]}" install --download-only -y "$@"; then
    sudo apt-get "${apt_options[@]}" install --no-download -y "$@"
    exit
  fi
  echo "Could not fetch QA packages from $mirror" >&2
done

echo 'Ubuntu QA packages could not be fetched from any configured mirror.' >&2
exit 1
