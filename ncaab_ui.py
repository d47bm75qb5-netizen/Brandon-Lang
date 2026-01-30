import streamlit as st
import pandas as pd
import json
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NCAAB AI Betting Agent",
    page_icon="🏀",
    layout="wide"
)

# --- LOAD DATA ---
def load_data():
    # 1. Load Picks (or create dummy if missing)
    if os.path.exists("ncaab_picks.json"):
        with open("ncaab_picks.json", "r") as f:
            picks = json.load(f)
    else:
        picks = {
            "date": "Pending", 
            "lock": "Pending", 
            "value": "Pending", 
            "analysis": "Data not ready. Please run the updater."
        }

    # 2. Load History (or create empty scoreboard if missing)
    if os.path.exists("ncaab_history.json"):
        with open("ncaab_history.json", "r") as f:
            history = json.load(f)
    else:
        history = {
            "lock": {"wins": 0, "losses": 0, "pushes": 0},
            "value": {"wins": 0, "losses": 0, "pushes": 0},
            "updated_date": ""
        }
    
    return picks, history

picks_data, history_data = load_data()

# --- SIDEBAR: THE SCOREBOARD ---
st.sidebar.markdown("## 🏆 **Betting Record**")

def calculate_win_rate(record):
    total = record['wins'] + record['losses']
    if total == 0:
        return "0%"
    win_pct = int((record['wins'] / total) * 100)
    return f"{win_pct}%"

# 1. Lock Record
lock_rec = history_data.get("lock", {"wins": 0, "losses": 0})
lock_wr = calculate_win_rate(lock_rec)
st.sidebar.metric(
    label="🔒 Lock Win %",
    value=lock_wr,
    delta=f"{lock_rec['wins']}W - {lock_rec['losses']}L"
)

# 2. Value Record
value_rec = history_data.get("value", {"wins": 0, "losses": 0})
value_wr = calculate_win_rate(value_rec)
st.sidebar.metric(
    label="🐕 Value Win %",
    value=value_wr,
    delta=f"{value_rec['wins']}W - {value_rec['losses']}L"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Last Updated: {picks_data.get('date', 'Unknown')}")

# --- MAIN PAGE UI ---
st.title("🏀 NCAAB AI Betting Agent")
st.subheader(f"📅 **Picks for {picks_data.get('date', 'Today')}**")

st.markdown("---")

# Layout: Two Columns for the Picks
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🔒 **LOCK OF THE DAY**")
    # Blue Box for the Lock
    st.info(f"## {picks_data.get('lock', 'Pending')}")

with col2:
    st.markdown("### 🐕 **VALUE PLAY**")
    # Green Box for the Value Play
    st.success(f"## {picks_data.get('value', 'Pending')}")

st.markdown("---")

# Analysis Section
st.subheader("📝 **The Breakdown**")
st.write(picks_data.get("analysis", "Analysis pending..."))
