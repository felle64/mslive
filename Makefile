PYTHON ?= python
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: venv dash dash-replay log

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install -U pip
	$(VENV_PIP) install -e .

dash:
	@if [ -z "$(PORT)" ]; then echo "Usage: make dash PORT=/dev/ttyUSB0"; exit 1; fi
	$(VENV_PY) -m mslive.apps.dash_tk3 --port "$(PORT)"

dash-replay:
	@if [ -z "$(FILE)" ]; then echo "Usage: make dash-replay FILE=logs/ms42_dash_YYYYmmdd_HHMMSS.csv"; exit 1; fi
	$(VENV_PY) -m mslive.apps.dash_tk3 --replay "$(FILE)"

log:
	@if [ -z "$(PORT)" ]; then echo "Usage: make log PORT=/dev/ttyUSB0"; exit 1; fi
	$(VENV_PY) -m mslive.apps.logger_csv --port "$(PORT)"
