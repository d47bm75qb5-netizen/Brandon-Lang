import streamlit as st
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Brandon Lang: NBA Edition", page_icon="🏀", layout="wide")

# --- FILES ---
PICKS_FILE = "picks.json"
HISTORY_FILE = "history.json"

# --- LOAD DATA ---
def load_data():
    # Load Picks
    if os.path.exists(PICKS_FILE):
        with open(PICKS_FILE, "r") as f:
            picks = json.load(f)
    else:
        picks = None

    # Load History (for Win %)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    else:
        # Default blank history if file doesn't exist yet
        history = {
            "lock": {"wins": 0, "losses": 0, "pushes": 0},
            "value": {"wins": 0, "losses": 0, "pushes": 0}
        }
    return picks, history

def calculate_win_pct(record):
    total = record['wins'] + record['losses'] # Pushes don't count towards %
    if total == 0:
        return "0%"
    return f"{int((record['wins'] / total) * 100)}%"

# --- MAIN APP ---
picks, history = load_data()

# --- SIDEBAR (The Record) ---
with st.sidebar:
    st.header("🏆 Season Record")
    
    # Lock Stats
    lock_pct = calculate_win_pct(history['lock'])
    st.metric(
        label="🔒 Lock Win %", 
        value=lock_pct, 
        delta=f"{history['lock']['wins']}-{history['lock']['losses']}"
    )
    
    # Value Stats
    value_pct = calculate_win_pct(history['value'])
    st.metric(
        label="🐕 Value Win %", 
        value=value_pct, 
        delta=f"{history['value']['wins']}-{history['value']['losses']}"
    )

    st.markdown("---")
    st.caption("Updated Daily at 9:00 AM CST")

# --- MAIN CONTENT ---
if picks:
    st.title("🏀 Brandon Lang: NBA Edition")
    st.subheader(f"📅 Picks for {picks.get('date', 'Today')}")
    st.markdown("---")

    # THE HEADLINES (Big Bold Picks)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 🔒 Lock of the Day")
        # Display the team name in big text
        st.markdown(f"## {picks.get('lock', 'Pending...')}")

    with col2:
        st.markdown("##### 🐕 Value Play")
        # Display the team name in big text
        st.markdown(f"## {picks.get('value', 'Pending...')}")

    st.markdown("---")

    # THE COMMENTARY
    # We replace newlines with double spaces to ensure markdown renders them as breaks
    analysis_text = picks.get('analysis', 'No analysis available.').replace("\n", "  \n")
    st.markdown(analysis_text)

else:
    st.warning("⚠️ Data not found. The bot is likely running its morning update. Check back in 5 minutes!")
