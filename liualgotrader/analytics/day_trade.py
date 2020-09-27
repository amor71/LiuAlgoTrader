import streamlit as st

st.title("Day-trade Session Analysis")
from datetime import date
start_day_to_analyze = st.date_input("Select trade day to analyze", value=date.today())

"Selected starting date:", start_day_to_analyze