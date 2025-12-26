# mslive (MS42 logger scaffold)

## Install (Linux or Windows)
python -m venv .venv

### Linux/macOS
source .venv/bin/activate

### Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -U pip
pip install -e .

## List ports
mslive ports

## Open port (no traffic yet, just sanity-check)
mslive open --port /dev/ttyUSB0
mslive open --port COM5

## Record raw TX/RX during a polling run
mslive poll --port /dev/ttyUSB0 --baud 10400 --poll-file polls/example.json --record session.mslr

## Replay a recorded session (no car needed)
mslive replay --file session.mslr
