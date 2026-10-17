import streamlit as st

from data import load_data

st.set_page_config(
    page_title="Harbourview Dashboards",
    page_icon="🏥",
    layout="wide",
)

df = load_data()

if "referral_date" not in df.columns:
    st.error("The dataset does not contain a referral_date column needed for the FY filter.")
    st.stop()

# The fiscal-year filter lives here so both dashboards share it; pages read st.session_state["fiscal_year"].
st.sidebar.header("Dashboard Filters")
available_years = sorted(df["referral_date"].dropna().dt.year.unique().tolist())
st.sidebar.selectbox("Fiscal Year", available_years, index=len(available_years) - 1, key="fiscal_year")

page = st.navigation(
    [
        st.Page("views/funnel.py", title="Referral → Admission", default=True),
        st.Page("views/occupancy.py", title="Occupancy & Length of Stay"),
        st.Page("views/outcomes.py", title="Funder Outcomes"),
    ]
)
page.run()
