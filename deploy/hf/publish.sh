#!/bin/bash
# Publishes the current commit to a Hugging Face Space (Docker SDK).
#   deploy/hf/publish.sh https://huggingface.co/spaces/<user>/<space>
# Git asks for your Hugging Face username and, as the password, an access token with WRITE permission
# (huggingface.co/settings/tokens). Only files tracked by git are sent, so backend/.env never leaves your machine.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: $0 <space git url>"; exit 1; }
root="$(git rev-parse --show-toplevel)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git -C "$root" archive HEAD | tar -x -C "$tmp"
cp "$root/deploy/hf/Dockerfile" "$tmp/Dockerfile"
cp "$root/deploy/hf/README.md" "$tmp/README.md"
rm -rf "$tmp/.github" "$tmp/frontend/e2e"
cd "$tmp"
git init -q -b main
git add -A
git -c user.name=qagent -c user.email=qagent@example.com commit -q -m "Publish QAgent"
git push --force "$1" main
echo "Pushed. The Space now builds the image (about 10 minutes the first time); watch the Logs tab."
