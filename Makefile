.PHONY: install run test check-python

PYTHON ?= python3
VENV := .venv
PYTHON_VENV := $(VENV)/bin/python
PIP_VENV := $(VENV)/bin/pip

install: check-python
	$(PYTHON) -m venv $(VENV)
	$(PIP_VENV) install --upgrade pip
	$(PIP_VENV) install -r requirements.txt

# The pinned packages in requirements.txt need Python 3.12 or newer (numpy 2.5 is the strictest).
check-python:
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Python 3.12 or newer is required, found " + sys.version.split()[0] + ". Install it, then run: make install PYTHON=python3.12")'

run:
	$(PYTHON_VENV) -m streamlit run app.py

test:
	$(PYTHON_VENV) -m pytest -q
