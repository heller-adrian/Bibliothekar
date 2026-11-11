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
cat > "$sources" <<'EOF'
Types: deb
URIs: https://archive.ubuntu.com/ubuntu/
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: https://security.ubuntu.com/ubuntu/
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF

# The runner's mirror list can select azure.archive.ubuntu.com for every suite.
# Scope the official archive sources to these commands on the disposable runner.
apt_options=(
  -o "Dir::Etc::sourcelist=$sources"
  -o Dir::Etc::sourceparts=-
  -o APT::Update::Error-Mode=any
  -o Acquire::Retries=2
  -o Acquire::https::Timeout=20
)
sudo apt-get "${apt_options[@]}" update -qq
sudo apt-get "${apt_options[@]}" install -y "$@"
