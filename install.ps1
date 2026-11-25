# Copyright (c) 2026 unlimitedera. All Rights Reserved.
# Clipsurge installer for Windows 10/11.
#   irm unlimitedera.github.io/clipsurge | iex
# With options:
#   & ([scriptblock]::Create((irm unlimitedera.github.io/clipsurge))) -Dir D:\Clipsurge -Cpu
# Options: -Dir <folder>  -Cpu  -NoLaunch  -NoShortcut  -Branch <name>
function Install-Clipsurge {
param(
  [string]$Dir = $(if ($env:CLIPSURGE_DIR) { $env:CLIPSURGE_DIR } else { Join-Path $env:LOCALAPPDATA "Clipsurge" }),
  [string]$Branch = "main",
  [switch]$Cpu = [bool]$env:CLIPSURGE_CPU,
  [switch]$NoLaunch = [bool]$env:CLIPSURGE_NOLAUNCH,
  [switch]$NoShortcut = [bool]$env:CLIPSURGE_NOSHORTCUT
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
$Repo = "unlimitedera/Clipsurge"

function Step($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Green }
function Info($m) { Write-Host "    $m" -ForegroundColor Gray }
function Fail($m) { throw $m }
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }

Write-Host ""
Write-Host "Clipsurge installer" -ForegroundColor Green
Write-Host "Copyright (c) 2026 unlimitedera. All Rights Reserved."
Write-Host "Clipsurge is proprietary software. Installing and using it requires permission from the author (see LICENSE)."
Write-Host "Install folder: $Dir"

if ($env:OS -ne "Windows_NT") { Fail "This installer is for Windows." }

# ---------- 1. Python 3.11 ----------
function Find-Python311 {
  $cands = @()
  if (Have "py") { try { $p = & py -3.11 -c "import sys;print(sys.executable)" 2>$null; if ($p) { $cands += $p } } catch {} }
  foreach ($p in @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe", "C:\Program Files\Python311\python.exe")) { if (Test-Path $p) { $cands += $p } }
  if (Have "python") { $cands += (Get-Command python).Source }
  foreach ($c in $cands) {
    try { $v = & $c -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null; if ($v -eq "3.11") { return $c } } catch {}
  }
  return $null
}
Step "Checking Python 3.11"
$py = Find-Python311
if (-not $py) {
  Info "Python 3.11 not found. Installing it for your user only (no admin needed)."
  $done = $false
  if (Have "winget") {
    try { winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null; $done = $true } catch {}
  }
  $py = Find-Python311
  if (-not $py) {
    $exe = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
    Info "Downloading the Python installer from python.org"
    Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $exe
    Start-Process $exe -ArgumentList "/quiet","InstallAllUsers=0","PrependPath=0","Include_launcher=0","Include_test=0" -Wait
    $py = Find-Python311
  }
  if (-not $py) { Fail "Could not install Python 3.11. Install it from https://www.python.org/downloads/release/python-3119/ and run this again." }
}
Info "Using $py"

# ---------- 2. Clipsurge files ----------
Step "Downloading Clipsurge ($Branch)"
$zip = Join-Path $env:TEMP "clipsurge-$([guid]::NewGuid().ToString('N').Substring(0,8)).zip"
$tmp = Join-Path $env:TEMP "clipsurge-src-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$sha = $null
try { $sha = (Invoke-RestMethod "https://api.github.com/repos/$Repo/commits/$Branch" -Headers @{ "User-Agent" = "Clipsurge-installer" }).sha } catch {}
$ref = if ($sha) { $sha } else { "refs/heads/$Branch" }
try { Invoke-WebRequest "https://github.com/$Repo/archive/$ref.zip" -OutFile $zip }
catch { Fail "Could not download from GitHub. Check your internet connection. ($($_.Exception.Message))" }
Expand-Archive $zip -DestinationPath $tmp -Force
$src = Get-ChildItem $tmp -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$upgrade = Test-Path (Join-Path $Dir "clipsurge")
# robocopy keeps your videos, settings and keys: data, secrets, .venv and tools are never touched
robocopy $src.FullName $Dir /E /XD data secrets .venv tools /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "Could not copy files into $Dir" }
Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
if ($sha) { Set-Content -Path (Join-Path $Dir ".version") -Value ('{"sha":"' + $sha + '","date":"' + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") + '"}') -Encoding ASCII }
if ($upgrade) { Info "Updated the existing install. Your projects, settings and keys were kept." } else { Info "Installed to $Dir" }

# ---------- 3. ffmpeg ----------
Step "Checking ffmpeg"
function Find-Ffmpeg {
  if (Have "ffmpeg") { return $true }
  if (Test-Path "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffmpeg.exe") { return $true }
  if (Get-ChildItem (Join-Path $Dir "tools") -Filter "ffmpeg*" -Directory -ErrorAction SilentlyContinue | ForEach-Object { Test-Path (Join-Path $_.FullName "bin\ffmpeg.exe") } | Where-Object { $_ }) { return $true }
  return $false
}
if (-not (Find-Ffmpeg)) {
  Info "ffmpeg not found. Downloading a portable copy into the Clipsurge folder."
  $fz = Join-Path $env:TEMP "ffmpeg-win64.zip"
  try {
    Invoke-WebRequest "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" -OutFile $fz
    New-Item -ItemType Directory -Force -Path (Join-Path $Dir "tools") | Out-Null
    Expand-Archive $fz -DestinationPath (Join-Path $Dir "tools") -Force
    Remove-Item $fz -Force
  } catch {
    if (Have "winget") { try { winget install -e --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements | Out-Null } catch {} }
  }
  if (-not (Find-Ffmpeg)) { Fail "Could not install ffmpeg. Install it from https://www.gyan.dev/ffmpeg/builds/ and run this again." }
} else { Info "ffmpeg is ready" }

# ---------- 4. Python environment ----------
Step "Setting up the Python environment (this takes a few minutes the first time)"
$venv = Join-Path $Dir ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) { & $py -m venv $venv; if ($LASTEXITCODE) { Fail "Could not create the Python environment." } }
$vpy = Join-Path $venv "Scripts\python.exe"
& $vpy -m pip install --upgrade pip --quiet --disable-pip-version-check
Info "Installing the main packages"
& $vpy -m pip install -r (Join-Path $Dir "requirements.txt") --quiet --disable-pip-version-check
if ($LASTEXITCODE) { Fail "Package install failed. Run it again, or see docs/INSTALL.md (Troubleshooting)." }
Info "Installing the on-screen text reader"
& $vpy -m pip install -r (Join-Path $Dir "requirements-ocr.txt") --no-deps --quiet --disable-pip-version-check
if ($LASTEXITCODE) { Info "The on-screen text reader could not be installed. Gaming mode still works without it." }
$gpu = (-not $Cpu) -and (Have "nvidia-smi")
if ($gpu) {
  Info "NVIDIA graphics card found. Installing GPU speech libraries (large download)"
  & $vpy -m pip install -r (Join-Path $Dir "requirements-gpu.txt") --quiet --disable-pip-version-check
  if ($LASTEXITCODE) { Info "GPU libraries failed. Clipsurge will use the CPU for speech." }
} else { Info "No NVIDIA GPU (or -Cpu used). Speech to text will run on the CPU." }

# ---------- 5. Check it starts ----------
Step "Checking the install"
Push-Location $Dir
try { $check = & $vpy -c "import clipsurge.server, cv2, faster_whisper, yt_dlp; print('ok')" 2>&1 } finally { Pop-Location }
if (($check | Select-Object -Last 1) -ne "ok") { Write-Host ($check | Out-String); Fail "Clipsurge did not load. Please send the text above in a GitHub issue." }
Info "Everything loads"

# ---------- 6. Shortcuts ----------
if (-not $NoShortcut) {
  Step "Creating shortcuts"
  try {
    $sh = New-Object -ComObject WScript.Shell
    foreach ($loc in @([Environment]::GetFolderPath("Desktop"), (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))) {
      $lnk = $sh.CreateShortcut((Join-Path $loc "Clipsurge.lnk"))
      $lnk.TargetPath = (Join-Path $Dir "start.bat"); $lnk.WorkingDirectory = $Dir
      $lnk.IconLocation = (Join-Path $Dir "web\favicon.ico"); $lnk.WindowStyle = 7; $lnk.Description = "Clipsurge"
      $lnk.Save()
    }
    Info "Added Clipsurge to your Desktop and Start menu"
  } catch { Info "Could not create shortcuts (not important): $($_.Exception.Message)" }
}

Write-Host ""
Write-Host "Clipsurge is installed." -ForegroundColor Green
Write-Host "Start it any time from the Desktop shortcut, or run: $Dir\start.bat"
Write-Host "It opens at http://127.0.0.1:8420  (only this computer can reach it)."
if (-not $NoLaunch) { Start-Process (Join-Path $Dir "start.bat") -WorkingDirectory $Dir }
}

try { Install-Clipsurge @args }
catch {
  Write-Host ""
  Write-Host "Install stopped: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Nothing is broken: run the same command again, or see docs/INSTALL.md." -ForegroundColor Yellow
}
