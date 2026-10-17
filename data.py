from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "harbourview_residents.csv"

DATE_COLUMNS = ["referral_date", "intake_date", "admission_date", "discharge_date"]


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)

    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in ["current_status", "discharge_reason", "followup_6m", "followup_12m", "staff_note"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().str.lower()

    return df


def fiscal_year_bounds(year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """January–December fiscal year."""
    return pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")


def latest_data_date(df: pd.DataFrame) -> pd.Timestamp:
    return df[[c for c in DATE_COLUMNS if c in df.columns]].max().max()


def pct(numerator: int, denominator: int) -> float:
    return numerator / denominator * 100 if denominator else 0.0
