import os
import json
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from nba_api.stats.endpoints import leaguedashteamstats

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 1. GET NBA STATS (The Fuel) ---
def get_nba_stats():
    try:
        # Get latest advanced stats for all teams
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Base').get_data_frames()[0]
        
        # Keep only the important columns for betting
        df = stats[['TEAM_NAME', 'W_PCT', 'OFF_RATING', 'DEF_RATING', 'NET_RATING', 'PACE']]
        
        # Convert to a readable string for the AI
        return df.to_string(index=False)
    except Exception as e:
        return f"Error fetching NBA stats: {e}"

# --- 2. GET LIVE ODDS (The Market) ---
def get_live_odds():
    # 1. API Setup
    # Adjust to CST (UTC-6)
    today = datetime.now(timezone(timedelta(hours=-6))).date()
    
    # URL for NBA Odds
    url = 'https://api.the-odds-api.com/v4/sports/basketball_nba/odds'
    
    # --- THE FIX IS HERE: REMOVED PLAYER PROPS ---
    params = {
        'apiKey': ODDS_API_KEY, 
        'regions': 'us', 
        'markets': 'h2h,spreads,totals',  # Only requesting standard lines now
        'oddsFormat': 'american'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # Check for error messages from the API
        if isinstance(data, dict) and 'message' in data:
            return None, f"Odds API Error: {data['message']}"
            
        if not isinstance(data, list):
            return None, f"API returned unexpected format: {data}"

        # Filter for games happening TODAY
        games = []
        for g in data:
            game_time = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
            if game_time.astimezone(timezone(timedelta(hours=-6))).date() == today:
                games.append(g)
        
        if not games: 
            return None, "No NBA games found for today."
        
        # Format the odds for the AI
        results = []
        for g in games:
            home = g['home_team']
            away = g['away_team']
            bookmakers = g['bookmakers']
            
            # Get the first bookmaker's odds (usually DraftKings or FanDuel)
            if bookmakers:
                odds = json.dumps(bookmakers[0]['markets'])
                results.append(f"MATCHUP: {away} @ {home}\nODDS: {odds}")
            else:
                results.append(f"MATCHUP: {away} @ {home}\nODDS: No odds available yet.")
            
        return "\n\n".join(results), None
        
    except Exception as e: 
        return None, str(e)

def parse_response(text):
    lock, value = "See Analysis", "See Analysis"
    try:
        if "LOCK OF THE DAY" in text:
            parts = text.split("LOCK OF THE DAY")[1].split("VALUE PLAY")[0]
            for line in parts.split("\n"):
                if "Pick:" in line: lock = line.replace("Pick:", "").strip(); break
        if "VALUE PLAY" in text:
            parts = text.split("VALUE PLAY")[1]
            for line in parts.split("\n"):
                if "Pick:" in line: value = line.replace("Pick:", "").strip(); break
    except: pass
    return lock, value

# --- 3. THE BRAIN (Gemini AI) ---
def generate_nba_content():
    # Fetch Data
    stats_text = get_nba_stats()
    odds_text, error = get_live_odds()
    
    if error or not odds_text:
        return {"date": str(datetime.now().date()), "analysis": f"Error: {error}", "lock": "N/A", "value": "N/A"}

    # FAIL SAFE FOR MISSING KEY
    if not GEMINI_API_KEY:
        return {"date": str(datetime.now().date()), "analysis": "Error: GOOGLE_API_KEY not found in Secrets.", "lock": "Error", "value": "Error"}

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are Brandon Lang, the world's best sports handicapper.
    
    I have provided:
    1. The latest NBA Team Stats (Net Rating, Pace, etc.)
    2. The Live Betting Odds for today's games.
    
    INSTRUCTIONS:
    - Analyze the matchups. Look for teams with a high Net Rating playing teams with a low Net Rating.
    - Find "Market Inefficiencies" (e.g. a strong team is only a small favorite).
    - Ignore "public biases" and trust the math.
    
    OUTPUT FORMAT:
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
    
    # Save to the JSON file
    with open("picks.json", "w") as f:
        json.dump(data, f, indent=4)
        
    print("Success! NBA Picks saved to picks.json")
