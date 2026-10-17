import pandas as pd
import pytest

from stays import (
    build_stays,
    completed_only_curve,
    curve_median,
    daily_census,
    kaplan_meier,
    monthly_occupancy,
    undated_discharges,
)

AS_OF = pd.Timestamp("2025-01-31")


def residents(rows):
    df = pd.DataFrame(rows, columns=["resident_id", "admission_date", "discharge_date", "current_status"])
    for col in ["admission_date", "discharge_date"]:
        df[col] = pd.to_datetime(df[col])
    return df


@pytest.fixture
def df():
    return residents(
        [
            ("A", "2025-01-01", "2025-01-11", "discharged"),  # completed, 10 days
            ("B", "2025-01-21", None, "phase_1"),  # ongoing at cut-off, 10 days so far
            ("C", "2025-01-25", "2025-02-10", "alumni"),  # discharged after cut-off -> censored
            ("D", "2025-01-05", None, "discharged"),  # left, but no discharge date
            ("E", None, None, "not_admitted"),
            ("F", "2025-02-05", None, "phase_1"),  # admitted after cut-off
        ]
    )


def test_undated_discharges_flags_only_residents_who_left(df):
    assert undated_discharges(df)["resident_id"].tolist() == ["D"]


def test_build_stays_censors_at_cutoff(df):
    stays = build_stays(df, AS_OF).set_index("resident_id")
    assert stays.index.tolist() == ["A", "B", "C"]
    assert stays["discharged"].tolist() == [True, False, False]
    # A completed after 10 days; B and C count days so far up to the cut-off.
    assert stays["los_days"].tolist() == [10, 10, 6]
    assert (stays.loc[["B", "C"], "end_date"] == AS_OF + pd.Timedelta(days=1)).all()


def test_census_excludes_discharge_night(df):
    census = daily_census(build_stays(df, AS_OF), pd.Timestamp("2025-01-01"), AS_OF)
    assert census[pd.Timestamp("2025-01-10")] == 1  # A's last night
    assert census[pd.Timestamp("2025-01-11")] == 0  # A's discharge day
    assert census[AS_OF] == 2  # B and C still in a bed on the cut-off night


def test_monthly_occupancy_counts_bed_nights(df):
    monthly = monthly_occupancy(build_stays(df, AS_OF), pd.Timestamp("2025-01-01"), AS_OF, capacity=4).iloc[0]
    # A: 10 nights, B: 21 Jan–31 Jan = 11, C: 25 Jan–31 Jan = 7.
    assert monthly["bed_nights"] == 28
    assert monthly["peak_census"] == 2
    assert monthly["admissions"] == 3
    assert monthly["discharges"] == 1
    assert monthly["occupancy_pct"] == pytest.approx(28 / (4 * 31) * 100)


def test_kaplan_meier_matches_hand_calculation():
    # Stays: 2 (event), 3 (censored), 4 (event), 4 (event), 6 (censored)
    curve = kaplan_meier([2, 3, 4, 4, 6], [True, False, True, True, False])
    assert curve["days"].tolist() == [0, 2, 4, 6]
    # Day 2: 5 at risk, 1 event -> 0.8. Day 4: 3 at risk, 2 events -> 0.8 * 1/3.
    assert curve["survival"].tolist() == pytest.approx([1.0, 0.8, 0.8 / 3, 0.8 / 3])
    assert curve_median(curve) == 4


def test_kaplan_meier_without_censoring_equals_completed_only():
    durations = [5, 10, 10, 20]
    km = kaplan_meier(durations, [True] * 4)
    naive = completed_only_curve(durations)
    assert km["survival"].tolist() == pytest.approx(naive["survival"].tolist())


def test_censoring_raises_median_above_completed_only():
    # Short stays have ended; long ones are still open. Completed-only understates the typical stay.
    durations = [10, 20, 30, 40, 50, 60]
    observed = [True, True, True, False, False, False]
    assert curve_median(completed_only_curve([10, 20, 30])) == 20
    assert curve_median(kaplan_meier(durations, observed)) == 30


def test_curve_median_none_when_never_reached():
    assert curve_median(kaplan_meier([5, 10], [False, False])) is None
