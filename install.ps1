# 風之谷 · Wind Valley — Cindy theme installer (Windows)
# Downloads the latest release package and hands it to Cindy's native importer.
$ErrorActionPreference = 'Stop'
$url  = 'https://github.com/wztlink1013/cindy-theme-wind-valley/releases/latest/download/wind-valley.cindy'
$dest = Join-Path $env:TEMP 'wind-valley.cindy'

Write-Host 'Downloading 風之谷 · Wind Valley ...'
Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing

Write-Host 'Opening Cindy importer ...'
Start-Process -FilePath $dest

Write-Host ''
Write-Host 'Done. In Cindy: click 导入 / Import, then 设置 -> 外观 -> 主题 -> 風之谷 · Wind Valley'
