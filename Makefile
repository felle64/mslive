PYTHON ?= python
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: venv dash dash-replay dash-pygame dash-pygame-replay log

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install -U pip
	$(VENV_PIP) install -e .

dash:
	@if [ -z "$(PORT)" ]; then echo "Usage: make dash PORT=/dev/ttyUSB0"; exit 1; fi
	$(VENV_PY) -m mslive.apps.dash_pygame --port "$(PORT)"

dash-replay:
	@if [ -z "$(FILE)" ]; then echo "Usage: make dash-replay FILE=logs/ms42_dash_YYYYmmdd_HHMMSS.csv"; exit 1; fi
	$(VENV_PY) -m mslive.apps.dash_pygame --replay "$(FILE)"

dash-pygame:
	@if [ -z "$(PORT)" ]; then echo "Usage: make dash-pygame PORT=/dev/ttyUSB0"; exit 1; fi
	$(VENV_PY) -m mslive.apps.dash_pygame --port "$(PORT)"

dash-pygame-replay:
	@if [ -z "$(FILE)" ]; then echo "Usage: make dash-pygame-replay FILE=logs/ms42_dash_YYYYmmdd_HHMMSS.csv"; exit 1; fi
	$(VENV_PY) -m mslive.apps.dash_pygame --replay "$(FILE)"

log:
	@if [ -z "$(PORT)" ]; then echo "Usage: make log PORT=/dev/ttyUSB0"; exit 1; fi
	$(VENV_PY) -m mslive.apps.logger_csv --port "$(PORT)"
