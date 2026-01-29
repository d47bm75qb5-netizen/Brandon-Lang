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

# --- 1. GET NCAAB STATS (Sports Reference) ---
def get_ncaab_stats():
    """
    Scrapes Sports-Reference.com for CBB Ratings (SRS).
    SRS (Simple Rating System) is the best predictive metric for College.
    """
    try:
        # Fetch 2026 Stats (Matching your NBA Date)
        url = "https://www.sports-reference.com/cbb/seasons/2026-ratings.html"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        
        response = requests.get(url, headers=headers, timeout=15)
        
        # Parse HTML Table
        dfs = pd.read_html(response.text)
        if not dfs: return "Error: No table found."
        df = dfs[0]
        
        # Clean Data: CBB tables often repeat headers, so we remove those rows
        df = df[df['School'] != 'School']
        
        # Select Columns: School and SRS (Simple Rating System)
        # SRS is essentially "Point Differential adjusted for Strength of Schedule"
        if 'SRS' in df.columns:
            df = df[['School', 'SRS']]
        else:
            return f"Stats Format Changed. Columns: {df.columns.tolist()}"
        
        return df.to_string(index=False)
    except Exception as e:
        return f"Error fetching stats: {e}"

# --- 2. GET LIVE ODDS (NCAAB) ---
def get_live_odds():
    # FORCE US CENTRAL TIME (UTC-6)
    cst_now = datetime.now(timezone(timedelta(hours=-6)))
    today = cst_now.date()
    
    # URL for College Basketball Odds
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

# --- 3. THE "FIND ALL" PARSER ---
def parse_response(text):
    """
    Scans the text for ALL occurrences of 'Pick:' regardless of layout.
    """
    lock, value = "See Analysis", "See Analysis"
    try:
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
    --- TEAM SRS RATINGS (Simple Rating System) ---
    (Higher SRS is better. SRS = Point Differential + Strength of Schedule)
    {stats_text}
    
    --- TODAY'S ODDS ---
    {odds_text}
    
    INSTRUCTIONS:
    1. Compare SRS Ratings. A team with an SRS of 15.0 is significantly better than a team with SRS 5.0.
    2. LOCK OF THE DAY: Find the biggest mismatch between SRS and the Spread.
    3. VALUE PLAY: Find a good underdog with a decent SRS.
    4. WIN PROBABILITY: Calculate % chance of winning based on the SRS gap.
    
    STRICT OUTPUT FORMAT:
    1. LOCK OF THE DAY
    Pick: [Team Name] [Spread/Moneyline]
    Win Probability: [XX.X]%
    Confidence: [High/Medium]
    Analysis: [Reasoning using SRS]

    2. VALUE PLAY
    Pick: [Team Name] [Spread/Moneyline]
    Win Probability: [XX.X]%
    Analysis: [Reasoning using SRS]
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
    print("Success! NCAAB Picks saved.")
