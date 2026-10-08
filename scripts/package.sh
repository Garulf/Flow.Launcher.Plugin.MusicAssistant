#!/usr/bin/env bash
# Build the Flow Launcher plugin archive and print its path.
# Usage: scripts/package.sh [out_dir]   (default: dist)
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
out_dir="${1:-$root/dist}"
version="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["Version"])' "$root/data/plugin.json")"
build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT

cp -r "$root/src/." "$build_dir/"
cp -r "$root/data/." "$build_dir/"
cp "$root/LICENSE" "$build_dir/"
find "$build_dir" \( -name __pycache__ -o -name '*.log' \) -prune -exec rm -rf {} +

# Pure-python wheels only: the zip is built on Linux but runs on the user's Windows Python.
python3 -m pip install -r "$root/requirements.txt" \
  --target "$build_dir/plugin/site-packages" \
  --only-binary=:all: --platform any --python-version 3.11 --implementation py \
  --quiet --disable-pip-version-check

mkdir -p "$out_dir"
zip_path="$(cd "$out_dir" && pwd)/Flow.Launcher.Plugin.MusicAssistant-${version}.zip"
rm -f "$zip_path"
(cd "$build_dir" && zip -qr "$zip_path" .)
echo "$zip_path"
