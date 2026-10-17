# Harbourview Resident Dashboard

A Streamlit app with three dashboards over the resident data in the data folder, sharing one fiscal-year filter (January–December):

- **Referral → Admission**: funnel, conversion rates and time-in-stage.
- **Occupancy & Length of Stay**: monthly occupancy against bed capacity, and length of stay for completed and ongoing stays (Kaplan–Meier for censored stays).
- **Funder Outcomes**: 6- and 12-month follow-up outcomes for residents discharged in the year, with lost to follow-up as its own category, a denominator on every rate, and labelled best and worst cases.

## Project structure

- app.py — entry point: page config, shared fiscal-year filter, navigation
- views/funnel.py — Referral → Admission dashboard
- views/occupancy.py — Occupancy & Length of Stay dashboard
- views/outcomes.py — Funder Outcomes dashboard
- data.py — data loading and fiscal-year helpers
- stays.py — occupancy and length-of-stay logic (census, bed-nights, Kaplan–Meier), no Streamlit
- outcomes.py — follow-up outcome logic (due / not reached, best and worst case), no Streamlit
- tests/ — unit tests for stays.py and outcomes.py
- data/harbourview_residents.csv — resident dataset
- requirements.txt — Python dependencies

## Requirements

- Python 3.12 or newer, available as `python3`. `make install` checks this and stops with a message if it's older. To use a different interpreter, run `make install PYTHON=python3.12`.
- `make`. On macOS it comes with the Xcode command line tools (`xcode-select --install`). On Windows, use WSL.
- Python's `venv` module. It's built in on macOS and Windows; on Debian or Ubuntu install it with `sudo apt install python3-venv`.

## Setup

Run this from the project root:

```bash
make install
```

This creates a local virtual environment and installs the exact package versions in requirements.txt, so everyone runs the same versions the app was tested with.

## Run

```bash
make run
```

Then open the URL shown in the terminal, typically:

```text
http://localhost:8501
```

## Test

```bash
make test
```
