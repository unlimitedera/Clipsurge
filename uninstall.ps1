# Copyright (c) 2026 unlimitedera. All Rights Reserved.
# Removes Clipsurge. Your videos and clips live in the data folder: you are asked before it is deleted.
param([string]$Dir = (Join-Path $env:LOCALAPPDATA "Clipsurge"))
if (-not (Test-Path $Dir)) { Write-Host "Nothing to remove at $Dir"; exit 0 }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*clipsurge.server*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
$data = Join-Path $Dir "data"
$keep = $false
if (Test-Path $data) {
  $a = Read-Host "Delete your projects, videos and clips in $data ? (y/N)"
  if ($a -ne "y") { $keep = $true }
}
Get-ChildItem $Dir -Force | Where-Object { -not ($keep -and ($_.Name -in "data","secrets")) } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
foreach ($loc in @([Environment]::GetFolderPath("Desktop"), (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))) { Remove-Item (Join-Path $loc "Clipsurge.lnk") -ErrorAction SilentlyContinue }
if (-not $keep) { Remove-Item $Dir -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "Clipsurge removed." $(if ($keep) { "Your data was kept in $Dir" })
