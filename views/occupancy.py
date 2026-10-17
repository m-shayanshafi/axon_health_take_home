import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import fiscal_year_bounds, latest_data_date, load_data, pct
from stays import (
    build_stays,
    completed_only_curve,
    curve_median,
    kaplan_meier,
    monthly_occupancy,
    survival_at,
    undated_discharges,
)

KM_COLOR = "#2a78d6"
PEAK_COLOR = "#eb6834"
COMPLETED_COLOR = "#9aa1ad"
CAPACITY_COLOR = "#4c5360"

REASON_LABELS = {
    "completed": "Program completed",
    "self_discharge": "Self-discharge",
    "transfer": "Transfer",
    "administrative": "Administrative",
    "other": "Other",
}

df = load_data()
selected_year = st.session_state["fiscal_year"]
year_start, year_end = fiscal_year_bounds(selected_year)
latest_date = latest_data_date(df)

# Measure as of 31 Dec, like the funnel; if the data stops earlier, as of the last date we have.
as_of = min(year_end, latest_date)
capacity = int(df["bed_capacity"].dropna().iloc[0])

stays = build_stays(df, as_of)
undated = undated_discharges(df)
undated = undated[undated["admission_date"] <= as_of]
monthly = monthly_occupancy(stays, year_start, as_of, capacity)

# Length-of-stay cohort: stays admitted in the fiscal year (mirrors the funnel's referral cohort).
cohort = stays[stays["admission_date"] >= year_start]
completed = cohort[cohort["discharged"]]
ongoing = cohort[~cohort["discharged"]]
in_residence_at_cutoff = int((stays["end_date"] > as_of).sum())

km_curve = kaplan_meier(cohort["los_days"], cohort["discharged"])
completed_curve = completed_only_curve(completed["los_days"])
km_median = curve_median(km_curve)
completed_median = completed["los_days"].median() if len(completed) else None

st.title("Harbourview Occupancy & Length of Stay")
st.caption(
    f"Fiscal Year {selected_year}: January 1 to December 31 · {capacity} beds · measured as of {as_of:%d %b %Y} · "
    "stays still open on that date are censored, not treated as ended"
)

if latest_date < year_end:
    st.warning(
        f"Data only runs to {latest_date:%d %b %Y}, so this fiscal year is incomplete "
        "and its figures are provisional."
    )

first_admission = df["admission_date"].min()
if year_start < first_admission <= year_end:
    st.info(f"The first recorded admission is {first_admission:%d %b %Y}; earlier months show no residents.")

total_bed_nights = int(monthly["bed_nights"].sum())
available_bed_nights = int(monthly["available_bed_nights"].sum())
months_at_capacity = int((monthly["peak_census"] >= capacity).sum())


def days_label(days: float | None) -> str:
    return f"{days:.0f} days" if days is not None and pd.notna(days) else "Not reached"


col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric(
        "Average Occupancy",
        f"{pct(total_bed_nights, available_bed_nights):.1f}%",
        help="Occupied bed-nights / (beds × nights in the fiscal year up to the cut-off date)",
    )
    st.caption(f"{total_bed_nights:,} / {available_bed_nights:,} bed-nights")
with col2:
    st.metric("Peak Nightly Census", f"{int(monthly['peak_census'].max())} / {capacity}")
    st.caption(f"At capacity in {months_at_capacity} of {len(monthly)} months")
with col3:
    st.metric(
        f"In Residence on {as_of:%d %b}",
        f"{in_residence_at_cutoff:,}",
        help="Stays still open on the cut-off date. Their length of stay is censored.",
    )
    st.caption("Ongoing stays (censored)")
with col4:
    st.metric(
        "Median Stay, Completed Only",
        days_label(completed_median),
        help="Stays admitted this FY and discharged by the cut-off date. Biased short, because short stays "
        "finish first and long ones are still open.",
    )
    st.caption(f"n = {len(completed)} completed stays")
with col5:
    st.metric(
        "Median Stay, incl. Ongoing",
        days_label(km_median),
        help="Kaplan–Meier estimate over every stay admitted this FY. Ongoing stays count for their days so far, "
        "then are censored.",
    )
    st.caption(f"n = {len(cohort)} stays · {len(ongoing)} still open")

st.markdown("---")

st.subheader("1. Monthly Occupancy Against Bed Capacity")
st.caption("Bars show the average nightly census (bed-nights ÷ nights in the month). Marks show the busiest night.")

month_labels = [
    f"{m:%b}<br>{occ:.0f}%" for m, occ in zip(monthly["month"].dt.to_timestamp(), monthly["occupancy_pct"])
]
fig_occ = go.Figure()
fig_occ.add_bar(
    x=month_labels,
    y=monthly["avg_census"],
    name="Average nightly census",
    marker_color=KM_COLOR,
    customdata=monthly[["occupancy_pct", "bed_nights", "available_bed_nights", "admissions", "discharges"]],
    hovertemplate="Avg census %{y:.1f} beds (%{customdata[0]:.0f}%)<br>"
    "%{customdata[1]} / %{customdata[2]} bed-nights<br>"
    "%{customdata[3]} admitted · %{customdata[4]} discharged<extra></extra>",
)
fig_occ.add_scatter(
    x=month_labels,
    y=monthly["peak_census"],
    mode="markers",
    name="Peak nightly census",
    marker=dict(symbol="line-ew-open", size=30, line=dict(width=3, color=PEAK_COLOR)),
    hovertemplate="Peak night %{y} / " + str(capacity) + " beds<extra></extra>",
)
fig_occ.add_hline(
    y=capacity,
    line_dash="dash",
    line_color=CAPACITY_COLOR,
    annotation_text=f"Capacity {capacity}",
    annotation_position="top right",
)
fig_occ.update_layout(
    margin=dict(t=30, b=20, l=20, r=20),
    height=360,
    yaxis=dict(title="Beds", range=[0, capacity * 1.15]),
    legend=dict(orientation="h", y=1.12),
    bargap=0.4,
)
st.plotly_chart(fig_occ, width="stretch")

st.markdown("---")
left_col, right_col = st.columns([5, 4])

with left_col:
    st.subheader("2. How Long Residents Stay")
    st.caption(
        f"Share of FY{selected_year} admissions still in residence after N days. Open stays count up to "
        f"{as_of:%d %b}, then leave the denominator (tick marks)."
    )

    fig_km = go.Figure()
    fig_km.add_scatter(
        x=completed_curve["days"],
        y=completed_curve["survival"],
        mode="lines",
        line_shape="hv",
        line=dict(color=COMPLETED_COLOR, width=2, dash="dash"),
        name=f"Completed stays only (n = {len(completed)})",
        hovertemplate="Day %{x:.0f}: %{y:.0%} still in residence<extra>Completed only</extra>",
    )
    fig_km.add_scatter(
        x=km_curve["days"],
        y=km_curve["survival"],
        mode="lines",
        line_shape="hv",
        line=dict(color=KM_COLOR, width=2),
        name=f"Kaplan–Meier, incl. ongoing (n = {len(cohort)})",
        hovertemplate="Day %{x:.0f}: %{y:.0%} still in residence<extra>Kaplan–Meier</extra>",
    )
    fig_km.add_scatter(
        x=ongoing["los_days"],
        y=survival_at(km_curve, ongoing["los_days"]),
        mode="markers",
        marker=dict(symbol="line-ns-open", size=12, line=dict(width=2, color=KM_COLOR)),
        name=f"Still in residence on {as_of:%d %b} ({len(ongoing)})",
        hovertemplate="Open stay, %{x:.0f} days so far<extra></extra>",
    )
    fig_km.add_hline(y=0.5, line_dash="dot", line_color=COMPLETED_COLOR, line_width=1)
    for median, color, label in [(completed_median, COMPLETED_COLOR, "completed only"), (km_median, KM_COLOR, "KM")]:
        if median is not None and pd.notna(median):
            fig_km.add_shape(
                type="line", x0=median, x1=median, y0=0, y1=0.5, line=dict(color=color, dash="dot", width=1)
            )
            fig_km.add_annotation(
                x=median, y=0.02, text=f"{median:.0f} d", showarrow=False, xanchor="left", font=dict(color=color)
            )
    fig_km.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        height=380,
        xaxis=dict(title="Days since admission", rangemode="tozero"),
        yaxis=dict(title="Still in residence", tickformat=".0%", range=[0, 1.02]),
        legend=dict(orientation="h", y=-0.22),
    )
    st.plotly_chart(fig_km, width="stretch")

with right_col:
    st.subheader("3. Completed vs Ongoing Stays")
    st.caption(f"FY{selected_year} admissions. Completed means discharged by {as_of:%d %b %Y}.")

    by_reason = (
        completed.groupby("discharge_reason")["los_days"]
        .agg(Stays="size", Median="median")
        .sort_values("Stays", ascending=False)
    )
    by_reason.index = by_reason.index.map(lambda r: REASON_LABELS.get(r, str(r).replace("_", " ").title()))
    by_reason.loc["All completed"] = [len(completed), completed_median]
    by_reason["Median"] = by_reason["Median"].map(lambda d: f"{d:.0f} days" if pd.notna(d) else "–")
    st.dataframe(
        by_reason.rename_axis("Completed stays, by discharge reason").reset_index(),
        hide_index=True,
        width="stretch",
    )

    st.markdown(f"**Ongoing stays on {as_of:%d %b}: {len(ongoing)}**")
    if len(ongoing):
        st.caption(
            f"Days in residence so far, a lower bound, since these stays will run longer. "
            f"Median {ongoing['los_days'].median():.0f} days, longest {ongoing['los_days'].max():.0f} days."
        )
        days_so_far = ongoing["los_days"].sort_values()
        # Stack dots that land within a week of each other so none hide behind another.
        stack_level = days_so_far.groupby(days_so_far // 7).cumcount()
        fig_strip = go.Figure(
            go.Scatter(
                x=days_so_far,
                y=stack_level,
                mode="markers",
                marker=dict(size=10, color=KM_COLOR, line=dict(width=1.5, color="white")),
                hovertemplate="%{x:.0f} days so far<extra></extra>",
            )
        )
        fig_strip.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=130,
            xaxis=dict(title="Days so far", rangemode="tozero"),
            yaxis=dict(visible=False, range=[-0.8, stack_level.max() + 0.8]),
            showlegend=False,
        )
        st.plotly_chart(fig_strip, width="stretch")

if len(undated):
    st.warning(
        f"**Data quality:** {len(undated)} admitted resident{'s' if len(undated) != 1 else ''} left the house "
        f"according to their status, with no discharge date ({', '.join(undated['resident_id'])}). Excluded from "
        "occupancy and length of stay, because counting them as still in residence pushes the census above "
        "bed capacity."
    )

st.markdown("---")
with st.expander("ℹ️ Methodology note"):
    st.markdown(
        f"""
        - **Cut-off date:** figures are measured as of {as_of:%d %b %Y}, the end of the fiscal year (or the last
          date in the data, if earlier). This matches the funnel dashboard's year-end rule.
        - **Occupancy:** a resident fills a bed every night from admission up to, but not including, discharge.
          Stays with no discharge by the cut-off count through the cut-off. Average nightly census = bed-nights ÷
          nights in the month; occupancy = bed-nights ÷ ({capacity} beds × nights).
        - **Length-of-stay cohort:** stays admitted in the fiscal year.
        - **Completed stays:** discharged by the cut-off. Shown separately, but on their own they understate the
          typical stay, because short stays finish first while long ones are still open.
        - **Censored (still-active) stays:** included through a Kaplan–Meier estimate. Each open stay counts as
          "still in residence" for its days so far, then leaves the denominator. The Kaplan–Meier median is the
          headline figure. Open stays are also shown as days so far, labelled as a lower bound, and are never
          averaged in as if they had ended. A stay discharged after the cut-off is still treated as open.
        - **Excluded records:** residents whose status says they left (discharged, aftercare, alumni) but who have
          no discharge date. Their end date is unknown, so they are flagged rather than guessed.
        """
    )
