#!/usr/bin/env bash
# 風之谷 · Wind Valley — Cindy theme installer (macOS / Linux)
set -euo pipefail
url='https://github.com/wztlink1013/cindy-theme-wind-valley/releases/latest/download/wind-valley.cindy'
dest="${TMPDIR:-/tmp}/wind-valley.cindy"

echo 'Downloading 風之谷 · Wind Valley ...'
if command -v curl >/dev/null 2>&1; then
  curl -fL "$url" -o "$dest"
else
  wget -qO "$dest" "$url"
fi

echo 'Opening Cindy importer ...'
if command -v open >/dev/null 2>&1; then
  open "$dest"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$dest"
else
  echo "Open this file with Cindy: $dest"
fi

echo
echo 'Done. In Cindy: click 导入 / Import, then 设置 -> 外观 -> 主题 -> 風之谷 · Wind Valley'
