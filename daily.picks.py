import os
import json
import requests
import pandas as pd
import google.generativeai as genai
import re
from datetime import datetime, timezone, timedelta

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 1. GET NBA STATS (Basketball Reference) ---
def get_nba_stats():
    try:
        # Fetch 2026 Stats
        url = "https://www.basketball-reference.com/leagues/NBA_2026_ratings.html"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        
        response = requests.get(url, headers=headers, timeout=15)
        dfs = pd.read_html(response.text)
        if not dfs: return "Error: No table found."
        df = dfs[0]
        
        possible_cols = ['Team', 'ORtg', 'DRtg', 'NRtg']
        if set(possible_cols).issubset(df.columns):
            df = df[possible_cols]
        
        return df.to_string(index=False)
    except Exception as e:
        return f"Error fetching stats: {e}"

# --- 2. GET LIVE ODDS (CST FIXED) ---
def get_live_odds():
    # FORCE US CENTRAL TIME (UTC-6)
    # This prevents the "Tomorrow" bug
    cst_now = datetime.now(timezone(timedelta(hours=-6)))
    today = cst_now.date()
    
    url = 'https://api.the-odds-api.com/v4/sports/basketball_nba/odds'
    params = {'apiKey': ODDS_API_KEY, 'regions': 'us', 'markets': 'h2h,spreads,totals', 'oddsFormat': 'american'}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if not isinstance(data, list): return None, "Error fetching odds."

        games = []
        for g in data:
            try:
                # Convert Game Time to CST to match "Today"
                game_time = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
                game_cst = game_time.astimezone(timezone(timedelta(hours=-6))).date()
                
                # Only keep games happening TODAY (CST)
                if game_cst == today:
                    games.append(g)
            except: continue
        
        if not games: return None, f"No NBA games found for {today}."
        
        results = []
        for g in games:
            home, away = g['home_team'], g['away_team']
            odds = json.dumps(g['bookmakers'][0]['markets']) if g['bookmakers'] else "No Odds"
            results.append(f"MATCHUP: {away} @ {home}\nODDS: {odds}")
            
        return "\n\n".join(results), None
    except Exception as e: return None, str(e)

# --- 3. THE PARSER (Includes Win Probability) ---
def extract_pick(section_text):
    if not section_text: return "See Analysis"
    
    # Regex: Finds "Pick:", captures text, stops at "Win Probability", "Confidence" or newline
    match = re.search(r"(?:Pick|Selection|Bet)\s*[:\-]\s*(.*?)(?:\s+Win Probability|\s+Confidence|\s+Analysis|\n|$)", section_text, re.IGNORECASE)
    
    if match:
        clean = match.group(1).strip()
        return clean.replace("*", "").replace("`", "")
    return "See Analysis"

def parse_response(text):
    lock, value = "See Analysis", "See Analysis"
    try:
        if "VALUE PLAY" in text:
            parts = text.split("VALUE PLAY")
            lock = extract_pick(parts[0]) if "LOCK OF THE DAY" in parts[0] else "See Analysis"
            value = extract_pick(parts[1])
        else:
            lock = extract_pick(text) if "LOCK OF THE DAY" in text else "See Analysis"
    except Exception as e:
        print(f"Parsing Error: {e}")
    return lock, value

# --- 4. THE BRAIN ---
def generate_nba_content():
    # Use CST for the file date too
    cst_now = datetime.now(timezone(timedelta(hours=-6)))
    current_date = str(cst_now.date())

    stats_text = get_nba_stats()
    odds_text, error = get_live_odds()
    
    if error or not odds_text:
        return {"date": current_date, "analysis": f"Error: {error}", "lock": "N/A", "value": "N/A"}

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are Brandon Lang.
    
    Data:
    --- TEAM NET RATINGS (2026 Season) ---
    {stats_text}
    
    --- TODAY'S ODDS ---
    {odds_text}
    
    INSTRUCTIONS:
    1. Compare Net Ratings.
    2. LOCK OF THE DAY: Biggest mismatch.
    3. VALUE PLAY: Best underdog.
    4. WIN PROBABILITY: You MUST calculate a percentage chance of winning based on the Net Rating gap.
    
    STRICT OUTPUT FORMAT:
    1. LOCK OF THE DAY
    Pick: [Team Name] [Spread/Moneyline]
    Win Probability: [XX.X]%
    Confidence: [High/Medium]
    Analysis: [Reasoning]

    2. VALUE PLAY
    Pick: [Team Name] [Spread/Moneyline]
    Win Probability: [XX.X]%
    Analysis: [Reasoning]
    """
    
    try:
        analysis = model.generate_content(prompt).text
        lock, value = parse_response(analysis)

        return {
            "date": current_date,
            "analysis": analysis,
            "lock": lock,
            "value": value
        }
    except Exception as e:
        return {"date": current_date, "analysis": f"AI Error: {e}", "lock": "Error", "value": "Error"}

if __name__ == "__main__":
    print("Starting Analysis...")
    data = generate_nba_content()
    with open("picks.json", "w") as f:
        json.dump(data, f, indent=4)
    print("Success! Picks saved.")
