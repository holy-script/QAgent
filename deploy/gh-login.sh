#!/bin/bash
# Gets a throw-away GitHub CLI (no Homebrew, no admin rights) and signs it in with the device flow.
# Run once per machine (or after /tmp is cleared). It prints a one-time code: open https://github.com/login/device and enter it.
#   deploy/gh-login.sh
set -euo pipefail
DIR=/tmp/ghcli
mkdir -p "$DIR" && cd "$DIR"
if ! ls gh_*/bin/gh >/dev/null 2>&1; then
  arch=$(uname -m); [ "$arch" = "arm64" ] && asset="macOS_arm64.zip" || asset="macOS_amd64.zip"
  url=$(curl -s https://api.github.com/repos/cli/cli/releases/latest | python3 -c "import sys,json; print(next(a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('$asset')))")
  curl -sL -o gh.zip "$url" && unzip -q -o gh.zip
fi
GH=$(ls -d "$DIR"/gh_*/bin/gh | head -1)
export GH_CONFIG_DIR="$DIR/config"
if "$GH" auth status >/dev/null 2>&1; then echo "already signed in:"; "$GH" auth status 2>&1 | head -3; exit 0; fi
# scopes: codespace (start/stop/ports), repo (read the private repo)
printf '\n\n' | BROWSER=true "$GH" auth login -h github.com -p https -w -s codespace,repo --skip-ssh-key
