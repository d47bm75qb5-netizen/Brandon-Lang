import streamlit as st
import json
import os
import pandas as pd

# --- PAGE SETUP ---
st.set_page_config(page_title="Brandon Lang Super-Agent", layout="wide")
st.title("🤑 Brandon Lang Super-Agent")
st.caption("v24.0 • Automated Daily Picks • Verified Performance Tracking")

# --- LOAD HISTORY & CALCULATE STATS ---
HISTORY_FILE = 'history.json'
PICK_FILE = 'picks.json'

def calculate_stats(history_data):
    if not history_data:
        return 0, 0, 0, 0
    
    df = pd.DataFrame(history_data)
    
    # Calculate Lock Win %
    lock_wins = len(df[df['lock_result'] == 'WIN'])
    lock_total = len(df[df['lock_result'].isin(['WIN', 'LOSS'])])
    lock_pct = int((lock_wins / lock_total) * 100) if lock_total > 0 else 0
    
    # Calculate Value Win %
    val_wins = len(df[df['value_result'] == 'WIN'])
    val_total = len(df[df['value_result'].isin(['WIN', 'LOSS'])])
    val_pct = int((val_wins / val_total) * 100) if val_total > 0 else 0
    
    return lock_pct, lock_wins, lock_total, val_pct, val_wins, val_total

# --- SIDEBAR: PERFORMANCE TRACKER ---
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'r') as f:
        history = json.load(f)
    
    l_pct, l_w, l_t, v_pct, v_w, v_t = calculate_stats(history)
    
    st.sidebar.header("🏆 Season Record")
    st.sidebar.metric("🔒 Lock Win %", f"{l_pct}%", f"{l_w}-{l_t - l_w} Record")
    st.sidebar.metric("🐕 Value Win %", f"{v_pct}%", f"{v_w}-{v_t - v_w} Record")
    st.sidebar.markdown("---")
    
    # Optional: Show recent history in sidebar
    with st.sidebar.expander("Recent Results"):
        for item in history[:5]: # Show last 5
            st.write(f"**{item['date']}**")
            st.caption(f"🔒 {item['lock_result']} | 🐕 {item['value_result']}")

# --- MAIN DISPLAY (TODAY'S PICKS) ---
if os.path.exists(PICK_FILE):
    try:
        with open(PICK_FILE, 'r') as f:
            data = json.load(f)
        
        st.header(f"📅 Picks for {data.get('date', 'Today')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🔒 LOCK OF THE DAY", data.get('lock_of_the_day', "Pending..."))
        with col2:
            st.metric("🐕 VALUE PLAY", data.get('value_play', "Pending..."))

        st.markdown("---")
        st.subheader("🤖 The Edge Analysis")
        st.info(data.get('analysis', "No analysis available."))

    except json.JSONDecodeError:
        st.error("Error reading data.")
else:
    # --- WAITING STATE ---
    st.warning("⚠️ No picks available yet.")
    st.markdown("""
    **The Super-Agent runs automatically at:**
    - 🕛 **12:00 PM CST**
    - 🕔 **5:00 PM CST**
    
    *Check back after those times for the latest breakdown!*
    """)

# --- REFRESH BUTTON ---
if st.button("🔄 Check for New Updates"):
    st.rerun()
