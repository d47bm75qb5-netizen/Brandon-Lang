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

# --- 1. GET NCAAB STATS (Source: TeamRankings) ---
def get_ncaab_stats():
    """
    Scrapes TeamRankings for 'Predictive Ratings'.
    This is much more reliable for bots than Sports-Reference.
    """
    try:
        # URL for Predictive Ratings (Best for betting)
        url = "https://www.teamrankings.com/ncaa-basketball/ranking/predictive-by-other"
        
        # Headers to look like a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse HTML Table
        dfs = pd.read_html(response.text)
        if not dfs: return "Error: No table found."
        df = dfs[0]
        
        # TeamRankings format: Rank, Team, Rating, ...
        # We just want Team and Rating
        if 'Team' in df.columns and 'Rating' in df.columns:
            df = df[['Team', 'Rating']]
            return df.to_string(index=False)
        else:
            return f"Stats Format Changed. Columns: {df.columns.tolist()}"

    except Exception as e:
        return f"Error fetching stats: {e}"

# --- 2. GET LIVE ODDS (CST TIME) ---
def get_live_odds():
    # FORCE US CENTRAL TIME (UTC-6)
    cst_now = datetime.now(timezone(timedelta(hours=-6)))
    today = cst_now.date()
    
    url = 'https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds'
    params = {'apiKey': ODDS_API_KEY, 'regions': 'us', 'markets': 'h2h,spreads,totals', 'oddsFormat': 'american'}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if not isinstance(data, list): return None, "Error fetching odds."

        games = []
        for g in data:
            try:
                game_time = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
                game_cst = game_time.astimezone(timezone(timedelta(hours=-6))).date()
                if game_cst == today:
                    games.append(g)
            except: continue
        
        if not games: return None, f"No NCAAB games found for {today}."
        
        results = []
        for g in games:
            home, away = g['home_team'], g['away_team']
            odds = json.dumps(g['bookmakers'][0]['markets']) if g['bookmakers'] else "No Odds"
            results.append(f"MATCHUP: {away} @ {home}\nODDS: {odds}")
            
        return "\n\n".join(results), None
    except Exception as e: return None, str(e)

# --- 3. ROBUST PARSER ---
def parse_response(text):
    lock, value = "See Analysis", "See Analysis"
    try:
        # Finds "Pick:" or "Bet:" and stops at newlines or keywords
        pattern = r"(?:Pick|Selection|Bet)\s*[:\-]\s*(.*?)(?:\s+(?:Win Probability|Confidence|Analysis)|\n|$)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        if len(matches) >= 1:
            lock = matches[0].strip().replace("*", "").replace("`", "")
        if len(matches) >= 2:
            value = matches[1].strip().replace("*", "").replace("`", "")
    except Exception as e:
        print(f"Parsing Error: {e}")
    return lock, value

# --- 4. THE BRAIN ---
def generate_ncaab_content():
    cst_now = datetime.now(timezone(timedelta(hours=-6)))
    current_date = str(cst_now.date())

    stats_text = get_ncaab_stats()
    odds_text, error = get_live_odds()
    
    if error or not odds_text:
        return {"date": current_date, "analysis": f"Error: {error}", "lock": "N/A", "value": "N/A"}

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are Brandon Lang, expert College Basketball handicapper.
    
    Data:
    --- TEAM PREDICTIVE RATINGS (TeamRankings) ---
    (Higher Rating is better. Example: +15.0 is elite, +5.0 is average)
    {stats_text}
    
    --- TODAY'S ODDS ---
    {odds_text}
    
    INSTRUCTIONS:
    1. Compare Predictive Ratings. If Team A is Rated 15.0 and Team B is Rated 10.0, Team A should be a ~5 point favorite.
    2. LOCK OF THE DAY: Find the biggest mismatch between the Rating Difference and the Vegas Spread.
    3. VALUE PLAY: Find an underdog where the Rating gap is smaller than the points they are getting.
    4. WIN PROBABILITY: Calculate % chance of winning based on the Ratings.
    
    STRICT OUTPUT FORMAT:
    1. LOCK OF THE DAY
    Pick: [Team Name] [Spread/Moneyline]
    Win Probability: [XX.X]%
    Confidence: [High/Medium]
    Analysis: [Reasoning using Ratings]

    2. VALUE PLAY
    Pick: [Team Name] [Spread/Moneyline]
    Win Probability: [XX.X]%
    Analysis: [Reasoning using Ratings]
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
    print("Starting NCAAB Analysis...")
    data = generate_ncaab_content()
    with open("ncaab_picks.json", "w") as f:
        json.dump(data, f, indent=4)
    print("Success! Picks saved.")
