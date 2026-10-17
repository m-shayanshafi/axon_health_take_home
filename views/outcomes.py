import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import fiscal_year_bounds, latest_data_date, load_data, pct
from outcomes import (
    ENGAGED,
    LOST,
    MIN_DENOMINATOR,
    NOT_RECORDED,
    NOT_YET_DUE,
    OUTCOME_LABELS,
    RELAPSE,
    UNKNOWN,
    best_worst,
    classify_followup,
    discharge_cohort,
    rate_is_reportable,
    summarize,
)
from stays import undated_discharges

OUTCOME_COLORS = {
    ENGAGED: "#2a78d6",
    RELAPSE: "#eb6834",
    LOST: "#5b6270",
    UNKNOWN: "#9aa1ad",
    NOT_RECORDED: "#cdd1d8",
}
OUTCOME_ORDER = [ENGAGED, RELAPSE, LOST, UNKNOWN, NOT_RECORDED]

REASON_LABELS = {
    "completed": "Program completed",
    "self_discharge": "Self-discharge",
    "transfer": "Transfer",
    "administrative": "Administrative",
    "other": "Other",
}

FOLLOWUPS = [("6 months", "followup_6m", 6), ("12 months", "followup_12m", 12)]

df = load_data()
selected_year = st.session_state["fiscal_year"]
year_start, year_end = fiscal_year_bounds(selected_year)

# Follow-ups happen after the FY by definition and carry no dates of their own, so outcomes are read
# as recorded on the latest data date rather than on 31 Dec.
snapshot = latest_data_date(df)

cohort = discharge_cohort(df, year_start, year_end).copy()
for label, column, months in FOLLOWUPS:
    cohort[label] = classify_followup(cohort, column, months, snapshot)
summaries = {label: summarize(cohort[label]) for label, _, _ in FOLLOWUPS}
six = summaries["6 months"]


def ratio(n: int, d: int) -> str:
    """'46% · 19/41', or just '19/41' when the denominator is too small for a rate."""
    return f"{pct(n, d):.0f}% · {n}/{d}" if rate_is_reportable(d) else f"{n}/{d}"


st.title("Harbourview Funder Outcomes")
st.caption(
    f"Residents discharged in Fiscal Year {selected_year} (1 Jan to 31 Dec) · follow-up due 6 and 12 months after "
    f"discharge · outcomes as recorded on {snapshot:%d %b %Y}, the latest data"
)

st.info(
    "**How to read this page:** every rate is out of everyone whose follow-up was due, including people the house "
    "could not reach. Nobody is dropped from the denominator for being hard to contact."
)

if cohort.empty:
    st.warning(f"No residents with a discharge date in FY{selected_year}.")
    st.stop()

engaged_6m = best_worst(six, ENGAGED)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric(f"Discharged in FY{selected_year}", f"{len(cohort):,}")
    st.caption("All discharge reasons")
with col2:
    st.metric("Due for 6-Month Follow-Up", f"{six['due']:,}")
    st.caption(f"{six[NOT_YET_DUE]} not yet due")
with col3:
    st.metric("Reached at 6 Months", ratio(six["reached"], six["due"]))
    st.caption("Engaged or relapse reported")
with col4:
    st.metric("Not Reached at 6 Months", ratio(six["not_reached"], six["due"]))
    st.caption(f"{six[LOST]} lost · {six[UNKNOWN]} unknown · {six[NOT_RECORDED]} not recorded")
with col5:
    if rate_is_reportable(engaged_6m["due"]):
        engaged_value = (
            f"{pct(engaged_6m['worst'], engaged_6m['due']):.0f}–{pct(engaged_6m['best'], engaged_6m['due']):.0f}%"
        )
    else:
        engaged_value = f"{engaged_6m['worst']}–{engaged_6m['best']} of {engaged_6m['due']}"
    st.metric(
        "Engaged in Recovery, 6 Months",
        engaged_value,
        help="Worst case: nobody not reached is engaged. Best case: everyone not reached is engaged.",
    )
    st.caption(f"Worst {engaged_6m['worst']}/{engaged_6m['due']} · best {engaged_6m['best']}/{engaged_6m['due']}")

st.markdown("---")

st.subheader("1. Outcomes at 6 and 12 Months")
st.caption(
    'Each bar is everyone whose follow-up was due. Lost to follow-up is its own category, not folded into "unknown" '
    f"or dropped. With fewer than {MIN_DENOMINATOR} people due, segments show counts only."
)

bar_labels = [f"{label}<br>n = {summaries[label]['due']} due" for label, _, _ in FOLLOWUPS]
fig_bars = go.Figure()
for outcome in OUTCOME_ORDER:
    counts = [summaries[label][outcome] for label, _, _ in FOLLOWUPS]
    dues = [summaries[label]["due"] for label, _, _ in FOLLOWUPS]
    fig_bars.add_bar(
        y=bar_labels,
        x=[pct(c, d) for c, d in zip(counts, dues)],
        orientation="h",
        name=OUTCOME_LABELS[outcome],
        marker=dict(
            color=OUTCOME_COLORS[outcome],
            pattern=dict(shape="/", fgcolor="white", solidity=0.3) if outcome == LOST else None,
        ),
        text=[ratio(c, d) if c else "" for c, d in zip(counts, dues)],
        textposition="inside",
        insidetextanchor="middle",
        customdata=list(zip(counts, dues)),
        hovertemplate=f"<b>{OUTCOME_LABELS[outcome]}</b><br>"
        + "%{customdata[0]} of %{customdata[1]} due<extra></extra>",
    )
fig_bars.update_layout(
    barmode="stack",
    height=260,
    margin=dict(t=20, b=20, l=20, r=20),
    xaxis=dict(title="Share of people due", ticksuffix="%", range=[0, 100]),
    yaxis=dict(autorange="reversed"),
    legend=dict(orientation="h", y=1.18, traceorder="normal"),
    bargap=0.35,
)
st.plotly_chart(fig_bars, width="stretch")
st.caption(
    " · ".join(
        f"{label}: {summaries[label][NOT_YET_DUE]} more discharged in FY{selected_year} "
        "but not yet due (not in the bar)"
        for label, _, _ in FOLLOWUPS
    )
)

st.markdown("---")

st.subheader("2. Best Case and Worst Case")
st.caption(
    "The true rate sits somewhere in each band. The worst case assumes everyone not reached had the bad outcome; "
    "the best case assumes they all had the good one."
)

range_rows = []
for label, _, _ in FOLLOWUPS:
    for reason, reason_label in [(None, "all discharges"), ("completed", "program completed"),
                                 ("self_discharge", "self-discharge")]:
        group = cohort if reason is None else cohort[cohort["discharge_reason"] == reason]
        bounds = best_worst(summarize(group[label]), ENGAGED)
        range_rows.append((f"Engaged in recovery, {label}<br>{reason_label}", bounds))
    range_rows.append((f"Relapse reported, {label}<br>all discharges", best_worst(summaries[label], RELAPSE)))

# A band needs a rate, so groups below the minimum denominator are listed as counts instead.
shown = [(name, b) for name, b in range_rows if rate_is_reportable(b["due"])]
counts_only = [(name, b) for name, b in range_rows if 0 < b["due"] < MIN_DENOMINATOR]

if shown:
    fig_range = go.Figure()
    for i, (name, b) in enumerate(shown):
        worst, best = pct(b["worst"], b["due"]), pct(b["best"], b["due"])
        color = OUTCOME_COLORS[RELAPSE] if name.startswith("Relapse") else OUTCOME_COLORS[ENGAGED]
        y_label = f"{name} (n = {b['due']})"
        fig_range.add_scatter(
            x=[min(worst, best), max(worst, best)],
            y=[y_label, y_label],
            mode="lines",
            line=dict(color=color, width=10),
            opacity=0.3,
            showlegend=False,
            hoverinfo="skip",
        )
        fig_range.add_scatter(
            x=[worst],
            y=[y_label],
            mode="markers+text",
            marker=dict(size=14, color="white", line=dict(width=3, color=color)),
            text=[f"<b>Worst case {worst:.0f}%</b> · {b['worst']}/{b['due']}"],
            textposition="top center",
            name="Worst case",
            legendgroup="worst",
            showlegend=i == 0,
            hovertemplate=f"Worst case: {b['worst']} of {b['due']}<extra></extra>",
        )
        fig_range.add_scatter(
            x=[best],
            y=[y_label],
            mode="markers+text",
            marker=dict(size=14, color=color),
            text=[f"<b>Best case {best:.0f}%</b> · {b['best']}/{b['due']}"],
            textposition="bottom center",
            name="Best case",
            legendgroup="best",
            showlegend=i == 0,
            hovertemplate=f"Best case: {b['best']} of {b['due']}<extra></extra>",
        )
    fig_range.update_layout(
        height=110 + 85 * len(shown),
        margin=dict(t=30, b=20, l=20, r=40),
        xaxis=dict(range=[-5, 105], ticksuffix="%", title="Share of people due"),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", y=1.06),
    )
    st.plotly_chart(fig_range, width="stretch")

if counts_only:
    st.caption(
        f"Fewer than {MIN_DENOMINATOR} people due, so counts only (worst–best): "
        + " · ".join(
            f"{name.replace('<br>', ', ')}: {b['worst']}–{b['best']} of {b['due']}"
            if name.startswith("Engaged")
            else f"{name.replace('<br>', ', ')}: {b['best']}–{b['worst']} of {b['due']}"
            for name, b in counts_only
        )
    )

st.markdown("---")

st.subheader("3. Outcomes by Discharge Reason")
st.caption(
    f"Counts, with the denominator (follow-up due) in the first column. Rates are hidden for groups with fewer than "
    f"{MIN_DENOMINATOR} people due."
)


def reason_table(label: str) -> pd.DataFrame:
    rows = []
    groups = [(REASON_LABELS.get(r, str(r).title()), g) for r, g in cohort.groupby("discharge_reason")]
    groups.sort(key=lambda item: -len(item[1]))
    for name, group in groups + [("All discharges", cohort)]:
        s = summarize(group[label])
        b = best_worst(s, ENGAGED)
        if b["due"] == 0:
            engaged_range = "–"
        elif rate_is_reportable(b["due"]):
            engaged_range = f"{pct(b['worst'], b['due']):.0f}% – {pct(b['best'], b['due']):.0f}%"
        else:
            engaged_range = f"n < {MIN_DENOMINATOR}"
        rows.append(
            {
                "Discharge reason": name,
                "Due": s["due"],
                "Engaged": s[ENGAGED],
                "Relapse": s[RELAPSE],
                "Lost": s[LOST],
                "Unknown": s[UNKNOWN],
                "Not recorded": s[NOT_RECORDED],
                "Engaged: worst – best": engaged_range,
                "Not yet due": s[NOT_YET_DUE],
            }
        )
    return pd.DataFrame(rows)


for tab, (label, _, _) in zip(st.tabs([label for label, _, _ in FOLLOWUPS]), FOLLOWUPS):
    with tab:
        st.dataframe(reason_table(label), hide_index=True, width="stretch")

reached_6m = six["reached"]
if reached_6m:
    survivorship = (
        f"Of the {reached_6m} people the house reached at 6 months, {six[ENGAGED]} were engaged in recovery "
        f"({pct(six[ENGAGED], reached_6m):.0f}%). Reporting that figure would leave out the {six['not_reached']} "
        "people nobody could reach, who are more likely to be struggling. That's survivorship bias. "
    )
else:
    survivorship = ""
st.error(
    f'**Why there is no "% sober" figure.** {survivorship}The honest figure is the worst-to-best range above, out of '
    f"all {six['due']} people due. The data records \"engaged in recovery\" and \"relapse reported\", not sobriety, "
    "so the page uses those words."
)

not_recorded_ids = sorted(
    set(cohort.loc[(cohort[[label for label, _, _ in FOLLOWUPS]] == NOT_RECORDED).any(axis=1), "resident_id"])
)
undated = undated_discharges(df)
notes = []
if not_recorded_ids:
    notes.append(
        f"{len(not_recorded_ids)} "
        f"{'residents were' if len(not_recorded_ids) != 1 else 'resident was'} due a follow-up with "
        f"no outcome recorded ({', '.join(not_recorded_ids)}). They count as not reached."
    )
if len(undated):
    notes.append(
        f"{len(undated)} resident{'s' if len(undated) != 1 else ''} with no discharge date "
        f"({', '.join(undated['resident_id'])}) can't be placed in a discharge year and are left out."
    )
if notes:
    st.warning("**Data quality:** " + " ".join(notes))

st.markdown("---")
with st.expander("ℹ️ Methodology note"):
    st.markdown(
        f"""
        - **Cohort:** everyone discharged in the fiscal year, whatever the reason (program completed, self-discharge,
          transfer, administrative, other). Program completers are shown as a breakdown, never as the headline.
        - **Snapshot date:** outcomes are read as recorded on {snapshot:%d %b %Y}, the latest date in the data. The
          dataset has no follow-up dates, so outcomes can't be rebuilt as of 31 Dec.
        - **Due:** a follow-up is due once 6 (or 12) months have passed since discharge, as of the snapshot date.
          People not yet due are counted and shown but sit outside every rate.
        - **Not reached:** lost to follow-up, unknown, and due but not recorded. All three stay in the denominator.
        - **Worst case:** everyone not reached counts as not engaged (or as relapsed). **Best case:** everyone not
          reached counts as engaged (or as not relapsed). Both are labelled wherever they appear.
        - **Small numbers:** with fewer than {MIN_DENOMINATOR} people due, the page shows counts only, because a
          rate on a handful of people is too unstable to report.
        - **Wording:** "engaged in recovery", never "sober". The data does not measure sobriety.
        """
    )
