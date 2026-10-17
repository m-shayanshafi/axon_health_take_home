# Harbourview Resident Dashboard

A Streamlit app with three dashboards over the resident data in the data folder, sharing one fiscal-year filter (January–December):

- **Referral → Admission**: funnel, conversion rates and time-in-stage.
- **Occupancy & Length of Stay**: monthly occupancy against bed capacity, and length of stay for completed and ongoing stays (Kaplan–Meier for censored stays).
- **Funder Outcomes**: 6- and 12-month follow-up outcomes for residents discharged in the year, with lost to follow-up as its own category, a denominator on every rate, and labelled best and worst cases.

## Requirements

- Python 3.12 or newer, available as `python3`. `make install` checks this and stops with a message if it's older.
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

## Task B: Agentic layer design

The design for the natural language → JSON spec → read-only query → chart flow is in these slides: [Task B design slides](https://docs.google.com/presentation/d/1Wnh1cbksFQffoIBoyDeV1AS0YBybN13WiX11BhnbPOk/edit?usp=sharing)

## Task C: Written answers

The Task C answers (C1 notes to structure, C2 accuracy, C3 predictive idea) are in this Google Doc: [Task C written answers](https://docs.google.com/document/d/1vjUkfCAx7fhcuWlzYYjg76e005a16P60J5911xsg54s/edit?usp=sharing)
