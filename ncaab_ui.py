import streamlit as st
import pandas as pd
import json
import os

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="NCAAB Super-Agent",
    page_icon="🏀",
    layout="wide"
)

# --- LOAD DATA ---
def load_data():
    # Load Picks
    if os.path.exists("ncaab_picks.json"):
        with open("ncaab_picks.json", "r") as f:
            picks = json.load(f)
    else:
        picks = {"date": "Pending", "lock": "Pending", "value": "Pending", "reasoning": "Pending"}

    # Load History (The New Scoreboard Format)
    if os.path.exists("ncaab_history.json"):
        with open("ncaab_history.json", "r") as f:
            history = json.load(f)
    else:
        history = {
            "lock": {"wins": 0, "losses": 0, "pushes": 0},
            "value": {"wins": 0, "losses": 0, "pushes": 0}
        }
    
    return picks, history

picks_data, history_data = load_data()

# --- SIDEBAR (SCOREBOARD) ---
st.sidebar.header("🏆 Betting Record")

def calculate_win_rate(record):
    total = record['wins'] + record['losses']
    if total == 0:
        return "0%"
    return f"{int((record['wins'] / total) * 100)}%"

# Lock Stats
lock_rec = history_data.get("lock", {"wins": 0, "losses": 0, "pushes": 0})
lock_wr = calculate_win_rate(lock_rec)
st.sidebar.metric("🔒 Lock Win %", lock_wr, f"{lock_rec['wins']}-{lock_rec['losses']}")

# Value Stats
value_rec = history_data.get("value", {"wins": 0, "losses": 0, "pushes": 0})
value_wr = calculate_win_rate(value_rec)
st.sidebar.metric("🐕 Value Win %", value_wr, f"{value_rec['wins']}-{value_rec['losses']}")

st.sidebar.markdown("---")
st.sidebar.write("Last Updated:", picks_data.get("date", "Unknown"))

# --- MAIN PAGE ---
st.title("🏀 Brandon Lang: March Madness Edition")
st.markdown(f"### 📅 **Picks for {picks_data.get('date', 'Today')}**")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🔒 **LOCK OF THE DAY**")
    st.info(f"## {picks_data.get('lock', 'Pending')}")

with col2:
    st.markdown("### 🐕 **VALUE PLAY**")
    st.success(f"## {picks_data.get('value', 'Pending')}")

st.markdown("---")
st.subheader("📝 The Breakdown")
st.write(picks_data.get("reasoning", "Analysis pending..."))
