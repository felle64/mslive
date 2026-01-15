# mslive (MS42 logger scaffold)

## Install (Linux or Windows)
python -m venv .venv

### Linux/macOS
source .venv/bin/activate

### Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -U pip
pip install -e .

## Quickstart (Linux/macOS)
```bash
make venv
make dash PORT=/dev/ttyUSB0
make log PORT=/dev/ttyUSB0
make dash-replay FILE=logs/ms42_dash_20260114_132209.csv
```

## Quickstart (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
.\scripts\run_dash.ps1 COM3
.\scripts\run_log.ps1 COM3
.\scripts\run_dash.ps1 --replay logs\ms42_dash_20260114_132209.csv
```

## Linux permissions note
If you get "permission denied" on Linux, add your user to the dialout group and re-login:
sudo usermod -a -G dialout $USER
You may also need a udev rule depending on your USB serial adapter.

## List ports
mslive ports

## Open port (no traffic yet, just sanity-check)
mslive open --port /dev/ttyUSB0
mslive open --port COM5

## Record raw TX/RX during a polling run
mslive poll --port /dev/ttyUSB0 --baud 10400 --poll-file polls/example.json --record session.mslr

## Replay a recorded session (no car needed)
mslive replay --file session.mslr

## Usage Examples
```bash
python -m mslive.apps.dash_pygame --replay logs/ms42_20260114_132209.csv --hz 10
python -m mslive.apps.logger_csv --replay logs/ms42_20260114_132209.csv --hz 10 --seconds 120
python -m mslive.apps.dash_pygame --port COM1 --baud 9600 --hz 10
```
Logs are written to `./logs/` by default. Relative paths passed to `--log` or `--out` are placed under `./logs/`.
