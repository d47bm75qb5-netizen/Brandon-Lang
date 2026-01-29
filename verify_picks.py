import os
import json
import requests
import re

# --- CONFIGURATION ---
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
PICKS_FILE = "picks.json"
HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {
        "lock": {"wins": 0, "losses": 0, "pushes": 0}, 
        "value": {"wins": 0, "losses": 0, "pushes": 0},
        "updated_date": ""
    }

def parse_pick_text(text):
    """
    Parses the pick into 3 types:
    1. ("Lakers", -5.0, "SPREAD")
    2. ("Warriors", None, "ML")
    3. ("Lakers/Celtics", 225.5, "OVER") or ("UNDER")
    """
    if not text or "Pending" in text or "Error" in text:
        return None, None, None

    text = text.lower()
    
    # 1. Check for Over/Under
    # Regex looks for "Over" or "Under" followed by a number
    ou_match = re.search(r"(over|under)\s+(\d+\.?\d*)", text)
    if ou_match:
        type_ = ou_match.group(1).upper() # "OVER" or "UNDER"
        line = float(ou_match.group(2))
        # For totals, the "Team" is less important, but we need to find the game
        # We'll use the first few words as the identifier
        identifier = text.split("over")[0].split("under")[0].strip()
        return identifier, line, type_

    # 2. Check for Moneyline/Spread
    # Regex to find team name and the number at the end
    match = re.search(r"^(.*?)\s+(?:moneyline|odds)?\s*[\(]?([+-]?\d+\.?\d*)[\)]?$", text)
    
    if match:
        team = match.group(1).strip().title() # Capitalize for matching
        number = float(match.group(2))
        
        # Large number = Moneyline Odds (e.g. -150), Small number = Spread (e.g. -5)
        if abs(number) >= 50: 
            return team, 0, "ML"
        else:
            return team, number, "SPREAD"
            
    # Fallback: Just a team name means Moneyline
    return text.strip().title(), 0, "ML"

def get_game_result(identifier, line, type_, scores):
    """
    Calculates WIN/LOSS based on the bet type.
    """
    for game in scores:
        if not game['completed']: continue
        
        h_team = game['home_team']
        a_team = game['away_team']
        
        # Fuzzy Match: Check if our identifier is in either team name
        # (e.g. "Lakers" is in "Los Angeles Lakers")
        identifier_clean = identifier.replace("Pick:", "").strip()
        
        if identifier_clean.lower() not in h_team.lower() and identifier_clean.lower() not in a_team.lower():
            continue # Not this game
            
        # Get Scores
        scores_list = game['scores']
        # Helper to find score by team name
        def get_score(name):
            for s in scores_list:
                if s['name'] == name: return int(s['score'])
            return 0

        h_score = get_score(h_team)
        a_score = get_score(a_team)
        
        # --- LOGIC BRANCHES ---
        
        # 1. OVER / UNDER
        if type_ in ["OVER", "UNDER"]:
            total_score = h_score + a_score
            if type_ == "OVER":
                if total_score > line: return "WIN"
                if total_score < line: return "LOSS"
            elif type_ == "UNDER":
                if total_score < line: return "WIN"
                if total_score > line: return "LOSS"
            return "PUSH"

        # 2. SPREAD / MONEYLINE
        # We need to know which team we picked to do the math
        if identifier_clean.lower() in h_team.lower():
            my_score = h_score
            opp_score = a_score
        else:
            my_score = a_score
            opp_score = h_score

        if type_ == "ML":
            if my_score > opp_score: return "WIN"
            if my_score < opp_score: return "LOSS"
            return "PUSH"
            
        elif type_ == "SPREAD":
            # (My Score + Spread) vs Opponent
            # e.g. Lakers (-5) vs Celtics. Lakers 105, Celtics 99.
            # 105 + (-5) = 100. 100 > 99. WIN.
            diff = (my_score + line) - opp_score
            if diff > 0: return "WIN"
            if diff < 0: return "LOSS"
            return "PUSH"

    return "UNKNOWN"

# --- EXECUTION ---
if __name__ == "__main__":
    if not os.path.exists(PICKS_FILE): exit()
    
    with open(PICKS_FILE, "r") as f:
        picks_data = json.load(f)

    history = load_history()
    
    if history.get("updated_date") == picks_data["date"]:
        print("Already updated.")
        exit()

    print("Fetching scores...")
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/scores/?daysFrom=3&apiKey={ODDS_API_KEY}"
    response = requests.get(url)
    scores_data = response.json()

    # Update Lock
    id_l, line_l, type_l = parse_pick_text(picks_data["lock"])
    if id_l:
        res = get_game_result(id_l, line_l, type_l, scores_data)
        if res == "WIN": history["lock"]["wins"] += 1
        elif res == "LOSS": history["lock"]["losses"] += 1
        elif res == "PUSH": history["lock"]["pushes"] += 1

    # Update Value
    id_v, line_v, type_v = parse_pick_text(picks_data["value"])
    if id_v:
        res = get_game_result(id_v, line_v, type_v, scores_data)
        if res == "WIN": history["value"]["wins"] += 1
        elif res == "LOSS": history["value"]["losses"] += 1
        elif res == "PUSH": history["value"]["pushes"] += 1

    history["updated_date"] = picks_data["date"]
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)
    
    print("Verification Complete.")
