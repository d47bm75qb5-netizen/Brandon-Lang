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

# --- 1. GET NBA STATS (The "TeamRankings" Version) ---
def get_nba_stats():
    """
    Scrapes TeamRankings.com for Net Efficiency.
    This source is lighter and less likely to block cloud bots.
    """
    try:
        # 1. URL for Net Efficiency Stats
        url = "https://www.teamrankings.com/nba/stat/net-efficiency"
        
        # 2. Simple Headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 3. Fetch
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 4. Parse HTML Table
        # (Pandas automatically finds the table)
        dfs = pd.read_html(response.text)
        df = dfs[0]
        
        # 5. Clean Data
        # TeamRankings format: "Rank", "Team", "2024", "Last 3", etc.
        # We just want "Team" and the current season rating (usually col index 2)
        df = df.iloc[:, [1, 2]] # Select Team Name and Current Rating
        df.columns = ['Team', 'Net_Rtg']
        
        return df.to_string(index=False)

    except Exception as e:
        return f"Error fetching stats: {e}"

# --- 2. GET LIVE ODDS ---
def get_live_odds():
    today = datetime.now(timezone(timedelta(hours=-6))).date()
    url = 'https://api.the-odds-api.com/v4/sports/basketball_nba/odds'
    params = {'apiKey': ODDS_API_KEY, 'regions': 'us', 'markets': 'h2h,spreads,totals', 'oddsFormat': 'american'}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if not isinstance(data, list): return None, "Error fetching odds."

        games = []
        for g in data:
            try:
                game_time = datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
                if game_time.astimezone(timezone(timedelta(hours=-6))).date() == today:
                    games.append(g)
            except: continue
        
        if not games: return None, "No NBA games found for today."
        
        results = []
        for g in games:
            home, away = g['home_team'], g['away_team']
            odds = json.dumps(g['bookmakers'][0]['markets']) if g['bookmakers'] else "No Odds"
            results.append(f"MATCHUP: {away} @ {home}\nODDS: {odds}")
            
        return "\n\n".join(results), None
    except Exception as e: return None, str(e)

# --- 3. THE PARSER (Fixed for One-Line Outputs) ---
def extract_pick(section_text):
    """
    Improved Regex to handle cases where Confidence/Analysis is on the same line.
    Example: "Pick: Wolves -9.0 Confidence: High..." -> Returns "Wolves -9.0"
    """
    if not section_text: return "See Analysis"
    
    # Regex Explanation:
    # 1. Look for "Pick:", "Selection:", or "Bet:"
    # 2. Capture everything until we hit "Confidence", "Analysis", or a new line
    match = re.search(r"(?:Pick|Selection|Bet)\s*[:\-]\s*(.*?)(?:\s+Confidence|\s+Analysis|\n|$)", section_text, re.IGNORECASE)
    
    if match:
        clean_text = match.group(1).strip()
        return clean_text.replace("*", "").replace("`", "")
    
    return "See Analysis"

def parse_response(text):
    lock, value = "See Analysis", "See Analysis"
    
    try:
        if "VALUE PLAY" in text:
            parts = text.split("VALUE PLAY")
            lock_section = parts[0]
            value_section = parts[1]
        else:
            lock_section = text
            value_section = ""

        if "LOCK OF THE DAY" in lock_section:
            lock = extract_pick(lock_section)
        
        if value_section:
            value = extract_pick(value_section)
            
    except Exception as e:
        print(f"Parsing Error: {e}")
        
    return lock, value

# --- 4. THE BRAIN ---
def generate_nba_content():
    stats_text = get_nba_stats()
    odds_text, error = get_live_odds()
    
    if error or not odds_text:
        return {"date": str(datetime.now().date()), "analysis": f"Error: {error}", "lock": "N/A", "value": "N/A"}

    if not GEMINI_API_KEY:
        return {"date": str(datetime.now().date()), "analysis": "Error: Missing Google API Key", "lock": "Error", "value": "Error"}

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are Brandon Lang.
    
    Data:
    --- TEAM EFFICIENCY STATS (Net Rating) ---
    {stats_text}
    
    --- TODAY'S ODDS ---
    {odds_text}
    
    INSTRUCTIONS:
    1. Compare Net Ratings. If a team with a +5.0 Net Rtg is playing a team with a -3.0 Net Rtg, that is a mismatch.
    2. LOCK OF THE DAY: The biggest statistical mismatch.
    3. VALUE PLAY: A team getting points (Underdog) that has a better Net Rating than their opponent.
    
    STRICT OUTPUT FORMAT:
    1. LOCK OF THE DAY
    Pick: [Team Name] [Spread/Moneyline]
    Confidence: [High/Medium]
    Analysis: [Your reasoning]

    2. VALUE PLAY
    Pick: [Team Name] [Spread/Moneyline]
    Analysis: [Your reasoning]
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
    print("Starting Analysis...")
    data = generate_nba_content()
    with open("picks.json", "w") as f:
        json.dump(data, f, indent=4)
    print("Done.")
