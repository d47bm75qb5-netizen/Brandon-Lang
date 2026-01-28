import streamlit as st
import json
import os

st.set_page_config(page_title="NCAAB Super-Agent", layout="wide")
st.title("🏀 Brandon Lang: March Madness Edition")

# READ THE COLLEGE FILE
PICK_FILE = 'ncaab_picks.json'

if os.path.exists(PICK_FILE):
    with open(PICK_FILE, 'r') as f:
        data = json.load(f)
    
    st.header(f"📅 Picks for {data.get('date')}")
    col1, col2 = st.columns(2)
    col1.metric("🔒 Lock of the Day", data.get('lock'))
    col2.metric("🐕 Value Play", data.get('value'))
    st.markdown("---")
    st.write(data.get('analysis'))
else:
    st.warning("⚠️ No College picks generated yet.")
