import pandas as pd
import plotly.express as px
import streamlit as st

from data import fiscal_year_bounds, latest_data_date, load_data, pct


def safe_duration_days(start: pd.Series, end: pd.Series) -> pd.Series:
    duration = (end - start).dt.days
    return duration.clip(lower=0)


# Staff notes on not-admitted referrals that mean the referral is still open
# (waiting on intake or a bed) rather than closed. All other notes are treated as closed.
OPEN_REFERRAL_NOTE_PATTERN = r"pending|waitlist"


def funnel_state_at(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    """Classify each referral as admitted / in_progress / closed on the as_of date."""
    admitted = df["admission_date"].notna() & (df["admission_date"] <= as_of)
    admitted_later = df["admission_date"] > as_of
    open_referral = (df["current_status"] == "not_admitted") & df["staff_note"].fillna("").str.contains(
        OPEN_REFERRAL_NOTE_PATTERN
    )
    state = pd.Series("closed", index=df.index)
    state[~admitted & (admitted_later | open_referral)] = "in_progress"
    state[admitted] = "admitted"
    return state


df = load_data()
selected_year = st.session_state["fiscal_year"]
year_start, year_end = fiscal_year_bounds(selected_year)

fy_df = df[(df["referral_date"] >= year_start) & (df["referral_date"] <= year_end)].copy()

st.title("Harbourview Referral to Admission Dashboard")
st.caption(f"Fiscal Year {selected_year}: January 1 to December 31 · funnel measured as of {year_end:%d %b %Y}")

latest_date = latest_data_date(df)
if latest_date < year_end:
    st.warning(
        f"Data only runs to {latest_date:%d %b %Y}, so this fiscal year is incomplete "
        "and its year-end figures are provisional."
    )

# Only count transitions that had happened by year end.
intake_by_ye = fy_df["intake_date"].where(fy_df["intake_date"] <= year_end)
admission_by_ye = fy_df["admission_date"].where(fy_df["admission_date"] <= year_end)
fy_df["funnel_state"] = funnel_state_at(fy_df, year_end)

referral_count = len(fy_df)
intake_count = intake_by_ye.notna().sum()
admission_count = admission_by_ye.notna().sum()
in_progress_count = (fy_df["funnel_state"] == "in_progress").sum()
closed_count = (fy_df["funnel_state"] == "closed").sum()

# Conversion rates use resolved referrals only (admitted or closed by year end),
# so cases still in progress don't count as failures.
resolved = fy_df["funnel_state"] != "in_progress"
resolved_count = resolved.sum()
resolved_intake_count = (resolved & intake_by_ye.notna()).sum()

ref_to_intake_rate = pct(resolved_intake_count, resolved_count)
intake_to_admission_rate = pct(admission_count, resolved_intake_count)
overall_conversion_rate = pct(admission_count, resolved_count)

# Range if every in-progress case ends up closed (low) or admitted (high).
low_conversion_rate = pct(admission_count, referral_count)
high_conversion_rate = pct(admission_count + in_progress_count, referral_count)

fy_df["ref_to_intake_days"] = safe_duration_days(fy_df["referral_date"], intake_by_ye)
fy_df["intake_to_admission_days"] = safe_duration_days(intake_by_ye, admission_by_ye)
fy_df["ref_to_admission_days"] = safe_duration_days(fy_df["referral_date"], admission_by_ye)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Referrals", f"{referral_count:,}")
with col2:
    st.metric("Intakes by 31 Dec", f"{intake_count:,}")
with col3:
    st.metric("Admissions by 31 Dec", f"{admission_count:,}")
with col4:
    st.metric(
        "Overall Conversion",
        f"{overall_conversion_rate:.1f}%",
        help=f"{admission_count} admitted / {resolved_count} resolved referrals (admitted or closed by 31 Dec)",
    )
    st.caption(f"{admission_count} / {resolved_count} resolved")
with col5:
    st.metric(
        "In Progress at 31 Dec",
        f"{in_progress_count:,}",
        help="Referred this year, not admitted by 31 Dec, and not closed: waitlisted, intake pending, "
        "or admitted after year end.",
    )

st.markdown("---")

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("1. Referral → Intake → Admission Funnel")

    funnel_df = pd.DataFrame(
        {
            "stage": ["Referral", "Intake", "Admission"],
            "value": [referral_count, intake_count, admission_count],
        }
    )

    fig_funnel = px.funnel(
        funnel_df,
        x="value",
        y="stage",
        color="stage",
        color_discrete_sequence=["#1f77b4", "#6baed6", "#2ca02c"],
    )
    fig_funnel.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        height=350,
        showlegend=False,
    )
    st.plotly_chart(fig_funnel, width="stretch")

    st.info(
        f"**Stage conversion (resolved referrals only):**\n"
        f"• Referral → Intake: **{ref_to_intake_rate:.1f}%** ({resolved_intake_count} / {resolved_count})\n"
        f"• Intake → Admission: **{intake_to_admission_rate:.1f}%** ({admission_count} / {resolved_intake_count})\n"
        f"• Overall (Referral → Admission): **{overall_conversion_rate:.1f}%** "
        f"({admission_count} / {resolved_count})\n\n"
        f"**Year-end status of {referral_count} referrals:** {admission_count} admitted · "
        f"{closed_count} closed · {in_progress_count} in progress\n\n"
        f"**Range:** {low_conversion_rate:.1f}% if no in-progress case is admitted "
        f"({admission_count} / {referral_count}), {high_conversion_rate:.1f}% if all are "
        f"({admission_count + in_progress_count} / {referral_count})"
    )

with right_col:
    st.subheader("2. Time-in-Stage")

    time_df = pd.DataFrame(
        {
            "Stage": [
                "Referral to Intake",
                "Intake to Admission",
                "Referral to Admission",
            ],
            "Median Days": [
                fy_df["ref_to_intake_days"].median(),
                fy_df["intake_to_admission_days"].median(),
                fy_df["ref_to_admission_days"].median(),
            ],
            "P90 Days": [
                fy_df["ref_to_intake_days"].quantile(0.90),
                fy_df["intake_to_admission_days"].quantile(0.90),
                fy_df["ref_to_admission_days"].quantile(0.90),
            ],
        }
    )

    time_plot_df = time_df.melt(
        id_vars="Stage",
        value_vars=["Median Days", "P90 Days"],
        var_name="Metric",
        value_name="Days",
    )

    fig_time = px.bar(
        time_plot_df,
        x="Days",
        y="Stage",
        color="Metric",
        barmode="group",
        orientation="h",
        color_discrete_map={"Median Days": "#1f77b4", "P90 Days": "#9ecae1"},
        text="Days",
    )
    fig_time.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig_time.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        height=350,
        xaxis_title="Days",
        yaxis_title="",
        showlegend=True,
    )
    st.plotly_chart(fig_time, width="stretch")

    st.success(
        "**Methodology:** times only include transitions completed by 31 Dec. Cases still waiting are left out, "
        "so these figures understate how long the slowest referrals take."
    )

st.markdown("---")
with st.expander("ℹ️ Methodology note"):
    st.markdown(
        """
        - The funnel is limited to the three stages the client cares about: Referral → Intake → Admission.
        - The dashboard uses a fiscal-year filter on referral dates to keep the analysis consistent for a January–December reporting period.
        - Each referral is classified by its state on 31 Dec of the fiscal year:
            - **Admitted:** admission date on or before 31 Dec.
            - **In progress:** not admitted by 31 Dec and not closed. This means admitted after 31 Dec, or still
              not admitted with a staff note saying intake is pending or the client is waitlisted.
            - **Closed:** everything else (no-show, declined, referred out, unreachable, not appropriate).
        - Conversion rates use resolved referrals only (admitted + closed). In-progress cases are shown as their own
          count and as a low/high range, rather than being counted as failures or admissions.
        - Assumptions: the data has no closure date, so a referral's current not-admitted note is taken as its state
          at year end. Notes that don't clearly say "pending" or "waitlist" are treated as closed.
        - Time-to-stage metrics only use valid, non-negative durations for transitions completed by 31 Dec.
        """
    )
