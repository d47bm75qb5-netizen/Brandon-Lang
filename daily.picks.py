import os
import json
import requests
import pandas as pd
import google.generativeai as genai
import re # Added for better text parsing
from datetime import datetime, timezone, timedelta

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 1. GET NBA STATS (The Fixed Version) ---
def get_nba_stats():
    """
    Fetches NBA stats using direct requests with headers to avoid timeouts/blocking.
    """
    try:
        # 1. Define the headers to look like a real browser (Critical for NBA.com)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.nba.com/',
            'Origin': 'https://www.nba.com',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        # 2. NBA Stats API Endpoint (LeagueDashTeamStats)
        url = "https://stats.nba.com/stats/leaguedashteamstats"
        params = {
            'MeasureType': 'Base',
            'PerMode': 'PerGame',
            'LeagueID': '00',
            'Season': '2024-25', # Auto-update this in future seasons
            'SeasonType': 'Regular Season',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'TeamID': '0',
            'Conference': '',
            'Division': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0'
        }

        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # 3. Parse the complicated JSON result
        headers_list = data['resultSets'][0]['headers']
        row_set = data['resultSets'][0]['rowSet']
        
        df = pd.DataFrame(row_set, columns=headers_list)
        
        # Keep only the important columns for betting
        df = df[['TEAM_NAME', 'W_PCT', 'OFF_RATING', 'DEF_RATING', 'NET_RATING', 'PACE']]
        
        return df.to_string(index=False)

    except Exception as e:
        return f"Error fetching NBA stats: {e}"

# --- 2. GET LIVE ODDS (The Market) ---
def get_live_odds():
    # Adjust to CST (UTC-6)
    today = datetime.now(timezone(timedelta(hours=-6))).date()
    url = 'https://api.the-odds-api.com/v4/sports/basketball_nba/odds'
    
    params = {
        'apiKey': ODDS_API_KEY, 
        'regions': 'us', 
        'markets': 'h2h,spreads,totals', 
        'oddsFormat': 'american'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if isinstance(data, dict) and 'message' in data:
            return None, f"Odds API Error: {data['message']}"
            
        if not isinstance(data, list):
            return None, f"API Error: {data}"

        games = []
        for g in data:
            game_time = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
            if game_time.astimezone(timezone(timedelta(hours=-6))).date() == today:
                games.append(g)
        
        if not games: 
            return None, "No NBA games found for today."
        
        results = []
        for g in games:
            home = g['home_team']
            away = g['away_team']
            bookmakers = g['bookmakers']
            
            if bookmakers:
                odds = json.dumps(bookmakers[0]['markets'])
                results.append(f"MATCHUP: {away} @ {home}\nODDS: {odds}")
            else:
                results.append(f"MATCHUP: {away} @ {home}\nODDS: No odds available yet.")
            
        return "\n\n".join(results), None
        
    except Exception as e: 
        return None, str(e)

# --- 3. PARSER (The Fixed Version) ---
def clean_pick_text(text):
    """Removes markdown formatting like ** or * from the pick."""
    if not text: return "See Analysis"
    # Remove asterisks, underscores, and leading/trailing spaces
    return text.replace("*", "").replace("_", "").strip()

def parse_response(text):
    lock, value = "See Analysis", "See Analysis"
    try:
        # Split into two main sections
        if "LOCK OF THE DAY" in text:
            parts = text.split("LOCK OF THE DAY")[1]
            
            # If VALUE PLAY exists, split by it to isolate the Lock
            if "VALUE PLAY" in parts:
                lock_section = parts.split("VALUE PLAY")[0]
                value_section = parts.split("VALUE PLAY")[1]
            else:
                lock_section = parts
                value_section = ""

            # Extract LOCK
            for line in lock_section.split("\n"):
                if "Pick:" in line:
                    raw_pick = line.split("Pick:")[1]
                    lock = clean_pick_text(raw_pick)
                    break
            
            # Extract VALUE
            if value_section:
                for line in value_section.split("\n"):
                    if "Pick:" in line:
                        raw_pick = line.split("Pick:")[1]
                        value = clean_pick_text(raw_pick)
                        break
                        
    except Exception as e:
        print(f"Parsing Error: {e}")
        
    return lock, value

# --- 4. THE BRAIN (Gemini AI) ---
def generate_nba_content():
    stats_text = get_nba_stats()
    odds_text, error = get_live_odds()
    
    if error or not odds_text:
        return {"date": str(datetime.now().date()), "analysis": f"Error: {error}", "lock": "N/A", "value": "N/A"}

    if not GEMINI_API_KEY:
        return {"date": str(datetime.now().date()), "analysis": "Error: GOOGLE_API_KEY not found.", "lock": "Error", "value": "Error"}

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are Brandon Lang, the world's best sports handicapper.
    
    I have provided:
    1. The latest NBA Team Stats (Net Rating, Pace, etc.)
    2. The Live Betting Odds for today's games.
    
    INSTRUCTIONS:
    - Analyze the matchups. Look for teams with a high Net Rating playing teams with a low Net Rating.
    - Find "Market Inefficiencies".
    
    OUTPUT FORMAT (STRICT):
    1. 🔒 LOCK OF THE DAY
       - Pick: [Team] [Spread/Moneyline]
       - Confidence: [High/Medium]
       - The Math: (Explain why the stats support this).

    2. 🐕 VALUE PLAY
       - Pick: [Team]
       - Why: (Why is the underdog live?)

    Data:
    --- TEAM STATS ---
    {stats_text}
    
    --- TODAY'S ODDS ---
    {odds_text}
    """
    
    try:
        analysis = model.generate_content(prompt).text
        lock, value = parse_response(analysis)

        return {
            "date": str(datetime.now().date()),
            "analysis": analysis,
            "lock": lock,
            "value": value
        }
    except Exception as e:
        return {"date": str(datetime.now().date()), "analysis": f"AI Error: {e}", "lock": "Error", "value": "Error"}

if __name__ == "__main__":
    print("Starting NBA Analysis...")
    data = generate_nba_content()
    with open("picks.json", "w") as f:
        json.dump(data, f, indent=4)
    print("Success! NBA Picks saved.")
