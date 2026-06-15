import streamlit as st

st.title("Care Gap Map")
st.caption("H3-aggregated trust-weighted score, with uncertainty visualised")

# TODO: capability + geography selectors -> services.gold.fetch_h3_scores()
# TODO: render via streamlit-keplergl with color = score, alpha = confidence
st.info("Map view placeholder — wire up to gold.h3_care_score")
