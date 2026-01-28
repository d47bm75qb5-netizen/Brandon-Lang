import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="NCAAB Super-Agent", layout="wide")
st.title("🏀 Brandon Lang: March Madness Edition")

# --- SIDEBAR TRACKER ---
HISTORY_FILE = 'ncaab_history.json'
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'r') as f:
        history = json.load(f)
        
    df = pd.DataFrame(history)
    if not df.empty:
        # Calculate Win %
        l_wins = len(df[df['lock_result'] == 'WIN'])
        l_total = len(df[df['lock_result'].isin(['WIN', 'LOSS'])])
        l_pct = int((l_wins / l_total) * 100) if l_total > 0 else 0
        
        v_wins = len(df[df['value_result'] == 'WIN'])
        v_total = len(df[df['value_result'].isin(['WIN', 'LOSS'])])
        v_pct = int((v_wins / v_total) * 100) if v_total > 0 else 0

        st.sidebar.header("🏆 Tournament Record")
        st.sidebar.metric("🔒 Lock Win %", f"{l_pct}%", f"{l_wins}-{l_total-l_wins}")
        st.sidebar.metric("🐕 Value Win %", f"{v_pct}%", f"{v_wins}-{v_total-v_wins}")

# --- MAIN DISPLAY ---
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
    st.info("Check back at 12:00 PM and 5:00 PM CST.")
