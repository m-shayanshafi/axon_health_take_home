import pandas as pd
import pytest

from outcomes import (
    ENGAGED,
    LOST,
    NOT_RECORDED,
    NOT_YET_DUE,
    RELAPSE,
    UNKNOWN,
    best_worst,
    classify_followup,
    discharge_cohort,
    rate_is_reportable,
    summarize,
)

SNAPSHOT = pd.Timestamp("2026-01-15")


@pytest.fixture
def cohort():
    df = pd.DataFrame(
        [
            ("A", "2025-01-10", "engaged_in_recovery"),
            ("B", "2025-02-01", "relapse_reported"),
            ("C", "2025-03-01", "lost_to_follow_up"),
            ("D", "2025-04-01", "unknown"),
            ("E", "2025-05-01", None),  # due, nothing recorded
            ("F", "2025-06-01", "not_yet_due"),  # due by date, stale value
            ("G", "2025-12-01", "not_yet_due"),  # not due until Jun 2026
            ("H", "2024-12-31", "engaged_in_recovery"),  # previous FY
        ],
        columns=["resident_id", "discharge_date", "followup_6m"],
    )
    df["discharge_date"] = pd.to_datetime(df["discharge_date"])
    return discharge_cohort(df, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"))


def test_cohort_is_discharges_in_fy(cohort):
    assert cohort["resident_id"].tolist() == ["A", "B", "C", "D", "E", "F", "G"]


def test_due_comes_from_discharge_date_not_recorded_value(cohort):
    categories = classify_followup(cohort, "followup_6m", 6, SNAPSHOT).tolist()
    assert categories == [ENGAGED, RELAPSE, LOST, UNKNOWN, NOT_RECORDED, NOT_RECORDED, NOT_YET_DUE]


def test_not_reached_stays_in_denominator(cohort):
    s = summarize(classify_followup(cohort, "followup_6m", 6, SNAPSHOT))
    assert s["due"] == 6  # not-yet-due G is outside the denominator
    assert s["reached"] == 2
    assert s["not_reached"] == 4  # lost + unknown + 2 not recorded
    assert s[NOT_YET_DUE] == 1


def test_best_and_worst_case_for_good_and_bad_outcomes(cohort):
    s = summarize(classify_followup(cohort, "followup_6m", 6, SNAPSHOT))
    assert best_worst(s, ENGAGED) == {"due": 6, "worst": 1, "best": 5}
    # For relapse the best case is the low number: only confirmed relapses.
    assert best_worst(s, RELAPSE) == {"due": 6, "worst": 5, "best": 1}


def test_worst_case_is_never_the_survivorship_rate(cohort):
    s = summarize(classify_followup(cohort, "followup_6m", 6, SNAPSHOT))
    survivorship_rate = s[ENGAGED] / s["reached"]
    b = best_worst(s, ENGAGED)
    assert b["worst"] / b["due"] < survivorship_rate


def test_minimum_denominator():
    assert not rate_is_reportable(9)
    assert rate_is_reportable(10)
