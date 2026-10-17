"""Occupancy and length-of-stay logic. Pure pandas, no Streamlit, so it can be unit tested.

Conventions:
- A resident occupies a bed on the night of every date from admission_date up to, but not
  including, discharge_date (a midnight census).
- Everything is measured as of a cut-off date (`as_of`). A stay with no discharge on or before
  `as_of` is ongoing and is right-censored at `as_of`, even if the data shows a later discharge.
"""

import numpy as np
import pandas as pd

# Statuses that mean the resident is still living in the house.
IN_RESIDENCE_STATUSES = ["phase_1", "phase_2", "phase_3"]


def undated_discharges(df: pd.DataFrame) -> pd.DataFrame:
    """Admitted residents who have left the house (per status) but have no discharge date.

    We can't place their end date, and counting them as still in residence pushes the census
    above bed capacity, so they are excluded from occupancy and length of stay.
    """
    admitted = df["admission_date"].notna()
    left_house = ~df["current_status"].isin(IN_RESIDENCE_STATUSES)
    return df[admitted & left_house & df["discharge_date"].isna()]


def build_stays(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """One row per stay admitted on or before `as_of`, as the stay looked on `as_of`.

    Adds:
    - discharged: True if discharged on or before `as_of` (an observed, completed stay)
    - end_date: exclusive end of the stay for the census (discharge date, or the day after `as_of`)
    - los_days: completed length of stay, or days so far for an ongoing (censored) stay
    """
    stays = df[df["admission_date"].notna() & (df["admission_date"] <= as_of)]
    stays = stays.drop(undated_discharges(df).index, errors="ignore")

    discharged = stays["discharge_date"].notna() & (stays["discharge_date"] <= as_of)
    end_date = stays["discharge_date"].where(discharged, as_of + pd.Timedelta(days=1))
    los_end = stays["discharge_date"].where(discharged, as_of)

    return stays.assign(
        discharged=discharged,
        end_date=end_date,
        los_days=(los_end - stays["admission_date"]).dt.days,
    )


def daily_census(stays: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Number of residents in a bed on the night of each date from start to end inclusive."""
    days = pd.date_range(start, end, freq="D")
    admitted = stays["admission_date"].to_numpy()[:, None]
    ended = stays["end_date"].to_numpy()[:, None]
    in_bed = (admitted <= days.to_numpy()) & (ended > days.to_numpy())
    return pd.Series(in_bed.sum(axis=0), index=days, name="census")


def monthly_occupancy(
    stays: pd.DataFrame, start: pd.Timestamp, as_of: pd.Timestamp, capacity: int
) -> pd.DataFrame:
    """Monthly bed-nights, average and peak nightly census, and occupancy against capacity.

    Months are cut at `as_of`, so a partial final month is averaged over the days observed.
    """
    census = daily_census(stays, start, as_of)
    month = census.index.to_period("M")
    monthly = census.groupby(month).agg(days="size", bed_nights="sum", peak_census="max")

    admission_month = stays["admission_date"].dt.to_period("M")
    discharge_month = stays.loc[stays["discharged"], "discharge_date"].dt.to_period("M")
    monthly["admissions"] = admission_month.value_counts().reindex(monthly.index, fill_value=0)
    monthly["discharges"] = discharge_month.value_counts().reindex(monthly.index, fill_value=0)

    monthly["available_bed_nights"] = monthly["days"] * capacity
    monthly["avg_census"] = monthly["bed_nights"] / monthly["days"]
    monthly["occupancy_pct"] = monthly["bed_nights"] / monthly["available_bed_nights"] * 100
    return monthly.rename_axis("month").reset_index()


def kaplan_meier(durations: pd.Series, observed: pd.Series) -> pd.DataFrame:
    """Kaplan–Meier estimate of the share of stays still ongoing after each number of days.

    `observed` is True for completed stays and False for censored (still-active) stays. A stay
    censored at day t counts as at risk at t, the usual convention. The curve starts at (0, 1)
    and is extended to the longest stay so censored tails are drawn.
    """
    durations = np.asarray(durations, dtype=float)
    observed = np.asarray(observed, dtype=bool)
    points = [(0.0, 1.0)]
    survival = 1.0
    for t in np.unique(durations[observed]):
        at_risk = (durations >= t).sum()
        events = ((durations == t) & observed).sum()
        survival *= 1 - events / at_risk
        points.append((t, survival))
    if len(durations) and durations.max() > points[-1][0]:
        points.append((durations.max(), survival))
    return pd.DataFrame(points, columns=["days", "survival"])


def completed_only_curve(durations: pd.Series) -> pd.DataFrame:
    """Share of completed stays still ongoing after each number of days (ignores censored stays)."""
    durations = np.sort(np.asarray(durations, dtype=float))
    points = [(0.0, 1.0)] + [(t, (durations > t).mean()) for t in np.unique(durations)]
    return pd.DataFrame(points, columns=["days", "survival"])


def curve_median(curve: pd.DataFrame) -> float | None:
    """First day the curve reaches 50% or below; None if it never does (too many censored stays)."""
    reached = curve.loc[curve["survival"] <= 0.5, "days"]
    return float(reached.iloc[0]) if len(reached) else None


def survival_at(curve: pd.DataFrame, days: pd.Series) -> np.ndarray:
    """Step-function value of the curve at each given day."""
    idx = np.searchsorted(curve["days"].to_numpy(), np.asarray(days, dtype=float), side="right") - 1
    return curve["survival"].to_numpy()[idx]
