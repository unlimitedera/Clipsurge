# Install Clipsurge

Clipsurge runs on Windows 10 and 11. The installer is a single PowerShell script.

> Clipsurge is proprietary software. Installing and using it needs written permission from the author. See [LICENSE](../LICENSE).

## The one command

1. Press the Windows key, type **PowerShell**, and open it. You do not need "Run as administrator".
2. Paste this and press Enter:

```powershell
irm unlimitedera.github.io/clipsurge | iex
```

3. Wait. The first install takes 5 to 15 minutes, mostly downloads. You will see green `==>` lines for each step.
4. When it says **Clipsurge is installed**, your browser opens at `http://127.0.0.1:8420`.

That is all. Next time, use the **Clipsurge** shortcut on your Desktop or Start menu.

### Download size

Measured on Windows, November 2026. Most of it is one time.

| Part | Download | On disk | When |
|---|---|---|---|
| Clipsurge itself | 2 MB | 5 MB | always |
| Python packages (video, speech, vision) | 200 MB | 720 MB | always |
| Python 3.11 | 26 MB | 100 MB | only if you do not have it |
| ffmpeg (portable copy) | 206 MB | 600 MB | only if you do not have it |
| NVIDIA GPU libraries | 1.3 GB | 2.0 GB | only if an NVIDIA graphics card is found (makes speech to text much faster) |
| Speech model, downloaded the first time you use it | 0.5 GB | 0.5 GB | *small*, the default |
| Bigger speech model | 3.1 GB | 3.1 GB | *large-v3*, used automatically for Arabic and other non-Latin languages |

**Typical totals:** about **0.9 GB** to download on a PC without an NVIDIA card, about **2.2 GB** with one. Allow **2 GB** free (no NVIDIA card) or **5 GB** (NVIDIA card plus the big speech model), plus room for your videos and clips.

The disk sizes for Python 3.11 and ffmpeg are estimates; the other figures were measured. Local AI models are optional and separate (a small one is about 0.4 GB).

## What the installer does

| Step | What happens |
|---|---|
| Python 3.11 | Uses the one you have, or installs it for your user only (through winget, or from python.org). Other Python versions are left alone. |
| Clipsurge files | Downloads this repository from GitHub into `%LOCALAPPDATA%\Clipsurge`. |
| ffmpeg | Uses yours, or downloads a portable copy into `Clipsurge\tools`. |
| Python packages | Creates a private environment in `Clipsurge\.venv` and installs everything into it. Nothing is installed system wide. |
| GPU libraries | If an NVIDIA card is found, installs the CUDA libraries that make speech to text fast. |
| Check | Starts Clipsurge's code once to make sure it loads. |
| Shortcuts | Desktop and Start menu. |

## Options

Add options after the command:

```powershell
& ([scriptblock]::Create((irm unlimitedera.github.io/clipsurge))) -Dir D:\Clipsurge -Cpu
```

| Option | Meaning |
|---|---|
| `-Dir <folder>` | Install somewhere else (default `%LOCALAPPDATA%\Clipsurge`). Pick a drive with plenty of space: videos are large. |
| `-Cpu` | Skip the NVIDIA libraries. Speech to text runs on the processor. |
| `-NoLaunch` | Do not start Clipsurge when the install ends. |
| `-NoShortcut` | Do not create shortcuts. |
| `-Branch <name>` | Install a different branch. |

You can also set them as environment variables before the one-line command: `$env:CLIPSURGE_DIR = "D:\Clipsurge"` and `$env:CLIPSURGE_CPU = "1"`. The same works for `CLIPSURGE_NOLAUNCH` and `CLIPSURGE_NOSHORTCUT`.

If the short link is ever blocked on your network, the long form does the same thing:

```powershell
irm https://raw.githubusercontent.com/unlimitedera/Clipsurge/main/install.ps1 | iex
```

If you saved the script as a file and PowerShell says scripts are disabled, run `powershell -ExecutionPolicy Bypass -File .\install.ps1`. The one-line command does not need this.

## Update

Clipsurge checks GitHub for new versions. When there is one, a lime **Update** button appears at the top of the page. Click it, read the list of changes, press **Update now**, and Clipsurge updates itself and restarts. It will not update while videos are processing. You can also use **Settings > About > Check for updates**, or turn the prompt off there.

You can still update by hand: run the same command again. It replaces the program files and keeps your `data` (projects, videos, clips, settings) and `secrets` (YouTube key) folders.

## Start and stop

- Start: the Desktop shortcut, or `start.bat` in the install folder. A console window stays open while Clipsurge runs.
- Stop: press **Stop** at the top right of the page, or close the console window.
- Only your own computer can open the page. It is not shared on your network.

## Uninstall

```powershell
irm https://raw.githubusercontent.com/unlimitedera/Clipsurge/main/uninstall.ps1 -OutFile uninstall.ps1
.\uninstall.ps1
```

It asks before deleting your projects and videos.

## Manual install

If you prefer to do it by hand:

```powershell
# 1. get the files (download the ZIP from GitHub and unzip, or use git)
git clone https://github.com/unlimitedera/Clipsurge.git
cd Clipsurge

# 2. a Python 3.11 environment (3.12 and newer are not supported yet)
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt --no-deps
.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt   # only with an NVIDIA card

# 3. ffmpeg must be on your PATH
winget install -e --id Gyan.FFmpeg

# 4. run
start.bat
```

## Where things are stored

| What | Where |
|---|---|
| Videos, transcripts, clips, projects | `Clipsurge\data` |
| Explorer friendly view (Project, Video) | `Clipsurge\data\library` |
| Settings | `Clipsurge\data\settings.json` |
| YouTube key and sign in | `Clipsurge\secrets` (never uploaded anywhere) |
| Downloaded speech and language models | `Clipsurge\data\models` |

Back up `data` and `secrets` if you want to keep your work.

## Troubleshooting

**"Install stopped: Could not download from GitHub"**: check your connection, VPN or firewall, then run the command again.

**A package fails to install**: run the command again (it continues where it stopped). If it keeps failing, open an issue and paste the red text.

**The page does not open**: open `http://127.0.0.1:8420` yourself. If the console window shows an error, send it in an issue.

**Port 8420 is in use**: set another port before starting: `set CLIPSURGE_PORT=8500` then `start.bat`.

**Speech to text is slow**: without an NVIDIA card it runs on the CPU. Use a smaller speech model in Settings > Speech and video, or install the GPU libraries.

**Antivirus complains about a download**: the installer only fetches from github.com, python.org and winget. If your antivirus blocks `pip`, allow the install folder.

**"Python was not found"** or version errors: install Python 3.11 yourself from python.org, then run the installer again.
