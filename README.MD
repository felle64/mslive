# mslive (MS42 pygame dash)

Single supported app:

```
python -m mslive.apps.dash_pygame
```

## Install (Linux or Windows)
```bash
python -m venv .venv
```

### Linux/macOS
```bash
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### Windows (PowerShell)
```powershell
.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
```

## Live (Windows)
```powershell
python -m mslive.apps.dash_pygame --port COM3 --baud 9600 --hz 10
```

## Live (Linux)
```bash
python -m mslive.apps.dash_pygame --port /dev/ttyUSB0 --baud 9600 --hz 10
```

## Replay (offline)
```bash
python -m mslive.apps.dash_pygame --replay logs/ms42_dash_20260114_132209.csv --hz 10
```

## Logging
By default the dash writes CSV logs to `./logs/` (e.g. `logs/ms42_dash_YYYYmmdd_HHMMSS.csv`).
Disable logging with `--no-log`.

## Linux permissions note
If you get "permission denied" on Linux, add your user to the dialout group and re-login:
```bash
sudo usermod -a -G dialout $USER
```
You may also need a udev rule depending on your USB serial adapter.
