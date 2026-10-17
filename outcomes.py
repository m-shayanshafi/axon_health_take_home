"""Follow-up outcome logic for the funder dashboard. Pure pandas, no Streamlit, so it can be unit tested.

Conventions:
- Cohort: everyone discharged in the fiscal year, whatever the discharge reason.
- A follow-up is due once 6 (or 12) months have passed since discharge, as of the snapshot date.
  People not yet due are counted but sit outside every rate.
- Among people who are due, "lost to follow-up", "unknown" and "due but not recorded" are all
  "not reached". They stay in the denominator; nobody is dropped for being hard to contact.
"""

import pandas as pd

ENGAGED = "engaged_in_recovery"
RELAPSE = "relapse_reported"
LOST = "lost_to_follow_up"
UNKNOWN = "unknown"
NOT_RECORDED = "not_recorded"
NOT_YET_DUE = "not_yet_due"

# Outcomes among people whose follow-up is due, in display order.
DUE_OUTCOMES = [ENGAGED, RELAPSE, LOST, UNKNOWN, NOT_RECORDED]
REACHED = [ENGAGED, RELAPSE]
NOT_REACHED = [LOST, UNKNOWN, NOT_RECORDED]

OUTCOME_LABELS = {
    ENGAGED: "Engaged in recovery",
    RELAPSE: "Relapse reported",
    LOST: "Lost to follow-up",
    UNKNOWN: "Unknown",
    NOT_RECORDED: "Due, not recorded",
    NOT_YET_DUE: "Not yet due",
}

# Below this many people due, show counts only: a rate on a handful of people is too unstable to report.
MIN_DENOMINATOR = 10


def discharge_cohort(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Everyone discharged between start and end inclusive. Undated discharges can't be placed and drop out."""
    return df[(df["discharge_date"] >= start) & (df["discharge_date"] <= end)]


def classify_followup(cohort: pd.DataFrame, column: str, months: int, as_of: pd.Timestamp) -> pd.Series:
    """Outcome category for each resident at one follow-up point.

    Due-ness comes from the discharge date, not the recorded value: not due -> not_yet_due;
    due with a recognised outcome -> that outcome; due with a blank or stale value -> not_recorded.
    """
    due = cohort["discharge_date"] + pd.DateOffset(months=months) <= as_of
    recorded = cohort[column].where(cohort[column].isin([ENGAGED, RELAPSE, LOST, UNKNOWN]))
    category = recorded.fillna(NOT_RECORDED).astype(object)
    category[~due] = NOT_YET_DUE
    return category


def summarize(categories: pd.Series) -> dict:
    """Counts per category plus the denominators every rate is built on."""
    counts = {c: int((categories == c).sum()) for c in DUE_OUTCOMES + [NOT_YET_DUE]}
    counts["due"] = sum(counts[c] for c in DUE_OUTCOMES)
    counts["reached"] = sum(counts[c] for c in REACHED)
    counts["not_reached"] = sum(counts[c] for c in NOT_REACHED)
    return counts


def best_worst(summary: dict, outcome: str) -> dict:
    """Bounds for an outcome's rate when the people not reached could have gone either way.

    For a good outcome (engaged) the worst case counts nobody not reached as engaged and the best
    case counts all of them. For a bad outcome (relapse) it's the reverse.
    """
    confirmed = summary[outcome]
    if_all_unreached = confirmed + summary["not_reached"]
    good = outcome == ENGAGED
    return {
        "due": summary["due"],
        "worst": confirmed if good else if_all_unreached,
        "best": if_all_unreached if good else confirmed,
    }


def rate_is_reportable(denominator: int) -> bool:
    return denominator >= MIN_DENOMINATOR
