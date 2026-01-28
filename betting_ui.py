import streamlit as st
import json
import os

# --- PAGE SETUP ---
st.set_page_config(page_title="Brandon Lang Super-Agent", layout="wide")

st.title("🤑 Brandon Lang Super-Agent")
st.caption("v23.0 • Automated Daily Picks • Powered by AI")

# --- LOAD DATA LOGIC ---
PICK_FILE = 'picks.json'

if os.path.exists(PICK_FILE):
    try:
        with open(PICK_FILE, 'r') as f:
            data = json.load(f)
        
        # --- DISPLAY HEADER ---
        # Show the date the picks were generated for
        st.header(f"📅 Picks for {data.get('date', 'Today')}")
        
        # --- DISPLAY METRICS ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                label="🔒 LOCK OF THE DAY",
                value=data.get('lock_of_the_day', "Pending..."),
                delta="Top Confidence"
            )
            
        with col2:
            st.metric(
                label="🐕 VALUE PLAY",
                value=data.get('value_play', "Pending..."),
                delta="High Reward"
            )

        # --- DISPLAY ANALYSIS ---
        st.markdown("---")
        st.subheader("🤖 The Edge Analysis")
        
        analysis_text = data.get('analysis', "No analysis available.")
        st.info(analysis_text)

    except json.JSONDecodeError:
        st.error("Error reading the daily picks file. It might be generating right now.")
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
st.markdown("---")
if st.button("🔄 Check for New Updates"):
    st.rerun()
