import os
import json
import requests
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
import dateutil.parser

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- BARTTORVIK ADVANCED STATS ---
def get_barttorvik_stats():
    """
    Fetches T-Rank advanced stats (Adj Efficiency, etc.) for all teams.
    Returns a dictionary keyed by Team Name.
    """
    try:
        # Get data for the current season (2026 based on your context, using 2025/2026 logic)
        # Using 2024 as default for structure, but ideally this matches current year
        current_year = datetime.now().year
        if datetime.now().month > 4: current_year += 1 # Season flip logic
        
        url = f"https://barttorvik.com/{current_year}_team_results.json"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        stats_dict = {}
        for row in data:
            # Row index breakdown: [1]=Name, [6]=AdjOff, [8]=AdjDef, [21]=Win%
            team_name = row[1]
            stats_dict[team_name] = {
                "AdjOE": float(row[6]), # Adjusted Offensive Efficiency
                "AdjDE": float(row[8]), # Adjusted Defensive Efficiency
                "Barthag": float(row[2]) # Power Rating (0.0 to 1.0)
            }
        return stats_dict
    except Exception as e:
        print(f"Error fetching Barttorvik stats: {e}")
        return {}

def find_team_stats(team_name, stats_dict):
    """
    Simple fuzzy matcher to connect Odds API names to Barttorvik names.
    e.g. "Purdue Boilermakers" -> "Purdue"
    """
    # 1. Direct match
    if team_name in stats_dict: return stats_dict[team_name]
    
    # 2. Partial match (e.g. "Duke" in "Duke Blue Devils")
    for key in stats_dict:
        if key in team_name or team_name in key:
            return stats_dict[key]
            
    return None

def get_live_odds():
    # 1. SETUP
    target_date = datetime.now(timezone(timedelta(hours=-6))).date()
    sport_key = "basketball_ncaab"
    
    # 2. GET ADVANCED STATS FIRST
    print("Fetching Barttorvik Advanced Stats...")
    advanced_stats = get_barttorvik_stats()
    
    # 3. GET ODDS
    url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds'
    params = {
        'apiKey': ODDS_API_KEY, 
        'regions': 'us', 
        'markets': 'h2h,spreads,totals', 
        'oddsFormat': 'american'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if not isinstance(data, list): return None, f"API Error: {data}"

        games = [g for g in data if dateutil.parser.isoparse(g['commence_time']).astimezone(timezone(timedelta(hours=-6))).date() == target_date]
        
        if not games: return None, "No NCAAB games found for today."
        
        # Limit to 15 games to save tokens
        games = games[:15]
        
        results = []
        for g in games:
            h_name, a_name = g['home_team'], g['away_team']
            
            # Match names to stats
            h_stats = find_team_stats(h_name, advanced_stats)
            a_stats = find_team_stats(a_name, advanced_stats)
            
            # Format the stats string
            h_info = f"{h_name} (AdjO: {h_stats['AdjOE']}, AdjD: {h_stats['AdjDE']})" if h_stats else h_name
            a_info = f"{a_name} (AdjO: {a_stats['AdjOE']}, AdjD: {a_stats['AdjDE']})" if a_stats else a_name
            
            results.append(f"MATCHUP: {a_info} @ {h_info}\nMARKETS: {json.dumps(g['bookmakers'][:1])}")
            
        return "\n\n".join(results), None
    except Exception as e: return None, str(e)

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

def generate_ncaab_content():
    games_text, error = get_live_odds()
    
    if error or not games_text:
        return {"date": str(datetime.now().date()), "analysis": f"Error: {error}", "lock": "N/A", "value": "N/A"}

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are the Brandon Lang of College Basketball (NCAAB).
    
    I have provided you with the betting lines AND the "Barttorvik" Advanced Stats for each team.
    - **AdjO**: Adjusted Offensive Efficiency (Points scored per 100 possessions).
    - **AdjD**: Adjusted Defensive Efficiency (Points allowed per 100 possessions).
    
    INSTRUCTIONS:
    1. Compare the Efficiency Margins. If Team A has a significantly better AdjO than Team B's AdjD, they have a massive edge.
    2. Look for "Trap Lines" where the Efficiency stats suggest a team is much better than the spread indicates.
    3. Calculate a Win Probability based on these efficiency metrics.
    
    OUTPUT FORMAT:
    1. 🔒 LOCK OF THE DAY
       - Pick: [Team/Total] [Line]
       - Win Probability: [XX.X]%
       - The Math: (Use the AdjO/AdjD numbers to explain why this mismatch exists).

    2. 🐕 VALUE PLAY
       - Pick: [Team/Total]
       - Breakdown: (Why is the market wrong about this team's efficiency?)

    Data:
    {games_text}
    """
    
    analysis = model.generate_content(prompt).text
    lock, value = parse_response(analysis)

    return {
        "date": str(datetime.now().date()),
        "analysis": analysis,
        "lock": lock,
        "value": value
    }

if __name__ == "__main__":
    print("Starting NCAAB Analysis...")
    data = generate_ncaab_content()
    with open("ncaab_picks.json", "w") as f:
        json.dump(data, f, indent=4)
    print("Success! NCAAB Picks saved.")
