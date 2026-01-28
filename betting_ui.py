import streamlit as st
import google.generativeai as genai
import requests
import json
import pandas as pd
import random
from datetime import datetime, timedelta, timezone
import dateutil.parser

# --- CONFIGURATION ---
GEMINI_API_KEY = 'AIzaSyAwHrZ75XHclME7gEYUITCnk2e3iP8pFmA'
ODDS_API_KEY = 'f13de74f7a9205f925ea56b90a5ec3d8'
OPENWEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- WEATHER COORDINATES (NFL ONLY) ---
STADIUM_COORDS = {
    "Bills": {"lat": 42.7738, "lon": -78.7870}, "Chiefs": {"lat": 39.0489, "lon": -94.4839},
    "Packers": {"lat": 44.5013, "lon": -88.0622}, "Bears": {"lat": 41.8623, "lon": -87.6167},
    "Patriots": {"lat": 42.0909, "lon": -71.2643}, "Browns": {"lat": 41.5061, "lon": -81.6995},
    "Broncos": {"lat": 39.7439, "lon": -105.0201}, "Steelers": {"lat": 40.4468, "lon": -80.0158},
    "Eagles": {"lat": 39.9008, "lon": -75.1675}, "Seahawks": {"lat": 47.5952, "lon": -122.3316},
    "Giants": {"lat": 40.8128, "lon": -74.0742}, "Jets": {"lat": 40.8128, "lon": -74.0742},
    "Ravens": {"lat": 39.2780, "lon": -76.6227}, "Bengals": {"lat": 39.0955, "lon": -84.5161},
    "Titans": {"lat": 36.1665, "lon": -86.7713}, "Commanders": {"lat": 38.9076, "lon": -76.8645}
}

def get_game_weather(team_name, sport_key):
    if 'nba' in sport_key: return None
    coords = next((v for k, v in STADIUM_COORDS.items() if k in team_name), None)
    if not coords: return "N/A (Indoors)"
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={coords['lat']}&lon={coords['lon']}&appid={OPENWEATHER_API_KEY}&units=imperial"
    try:
        r = requests.get(url).json()
        return f"{r['weather'][0]['description'].title()} | 🌡️ {r['main']['temp']}°F | 💨 {r['wind']['speed']} mph"
    except: return "Weather Offline"

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_nba_stats():
    try:
        from nba_api.stats.endpoints import leaguedashteamstats
        return leaguedashteamstats.LeagueDashTeamStats(season='2025-26', measure_type_detailed_defense='Advanced').get_data_frames()[0]
    except: return pd.DataFrame()

def get_nba_metrics(team_name):
    stats = fetch_nba_stats()
    if stats.empty: return "Metrics: N/A"
    match = stats[stats['TEAM_NAME'].str.contains(team_name, case=False)]
    if not match.empty:
        return f"NetRtg: {match['NET_RATING'].values[0]} | Pace: {match['PACE'].values[0]}"
    return "Metrics: N/A"

@st.cache_data(ttl=3600)
def get_nfl_advanced_stats(team_name):
    try:
        import nfl_data_py as nfl
        df = nfl.import_pbp_data([2025], columns=['posteam', 'epa'])
        mapping = {'Patriots':'NE', 'Chiefs':'KC', 'Bills':'BUF', 'Cowboys':'DAL', 'Eagles':'PHI'}
        code = mapping.get(team_name.split()[-1], 'NE')
        return f"EPA/Play: {df[df['posteam'] == code]['epa'].mean():.3f}"
    except: return "Adv Stats: N/A"

# --- CORE LOGIC ---
def get_live_odds(sport_key, target_date):
    url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds'
    # Added 'totals' to the markets requested
    params = {'apiKey': ODDS_API_KEY, 'regions': 'us', 'markets': 'h2h,spreads,totals', 'oddsFormat': 'american'}
    try:
        data = requests.get(url, params=params).json()
        games = [g for g in data if dateutil.parser.isoparse(g['commence_time']).astimezone(timezone(timedelta(hours=-5))).date() == target_date]
        if not games: return None, "No games found."
        
        results = []
        for g in games:
            h, a = g['home_team'], g['away_team']
            weather = get_game_weather(h, sport_key)
            stats_h = get_nba_metrics(h) if 'nba' in sport_key else get_nfl_advanced_stats(h)
            stats_a = get_nba_metrics(a) if 'nba' in sport_key else get_nfl_advanced_stats(a)
            results.append(f"MATCHUP: {a} @ {h}\nWEATHER: {weather if weather else 'N/A'}\nSTATS: {a}({stats_a}) | {h}({stats_h})\nMARKETS: {json.dumps(g['bookmakers'][:1])}")
        return "\n\n".join(results), None
    except Exception as e: return None, str(e)

def get_brandon_lang_analysis(game_data, sport_key):
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are Brandon Lang. Use the data to find the ultimate edge.
    
    CRITICAL: 
    - You must now consider Over/Under (Totals) bets for your top picks.
    - If the Pace (NBA) or EPA/Weather (NFL) suggests a high-scoring blowout or a defensive slog, recommend the Over or Under if it's the strongest play on the board.
    
    Structure:
    1. 🔒 LOCK OF THE DAY
       - Pick: [Team/Over/Under]
       - Type: [MONEY LINE, SPREAD, or OVER/UNDER]
       - Win Probability: [%]
       - The Math: (Explain why this specific market is the superior tactical choice).

    2. 🐕 VALUE PLAY
       - Pick: [Team/Over/Under]
       - Type: [MONEY LINE, SPREAD, or OVER/UNDER]
       - Win Probability: [%]
       - Breakdown: (High-energy reasoning).

    Data:
    {game_data}
    """
    return model.generate_content(prompt).text

# --- UI SETUP ---
st.set_page_config(page_title="Brandon Lang Super-Agent", layout="wide")
st.title("🤑 Brandon Lang Super-Agent")
st.caption("v22.0 • Totals Integrated • Pure Math Edge Analysis")

col1, col2 = st.columns(2)
with col1: sport = st.selectbox("Sport Select", ("basketball_nba", "americanfootball_nfl"))
with col2: date = st.date_input("Date", datetime.now())

if st.button("⚡ Get Brandon's Best Picks", type="primary"):
    with st.spinner("Analyzing spreads, moneylines, and totals..."):
        games_text, error = get_live_odds(sport, date)
        if error: st.warning(error)
        elif games_text:
            st.success("Market Data Captured (including O/U).")
            st.markdown(get_brandon_lang_analysis(games_text, sport))
