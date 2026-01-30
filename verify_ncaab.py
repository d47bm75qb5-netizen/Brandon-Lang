import os
import json
import requests
import re

# --- CONFIGURATION ---
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
PICKS_FILE = "ncaab_picks.json"      # TARGETS NCAAB PICKS
HISTORY_FILE = "ncaab_history.json"  # TARGETS NCAAB HISTORY

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
    if not text or "Pending" in text or "Error" in text:
        return None, None, None

    text = text.lower()
    
    # 1. Check for Over/Under
    ou_match = re.search(r"(over|under)\s+(\d+\.?\d*)", text)
    if ou_match:
        type_ = ou_match.group(1).upper()
        line = float(ou_match.group(2))
        identifier = text.split("over")[0].split("under")[0].strip()
        return identifier, line, type_

    # 2. Check for Moneyline/Spread
    match = re.search(r"^(.*?)\s+(?:moneyline|odds)?\s*[\(]?([+-]?\d+\.?\d*)[\)]?$", text)
    if match:
        team = match.group(1).strip().title()
        number = float(match.group(2))
        if abs(number) >= 50: return team, 0, "ML"
        else: return team, number, "SPREAD"
            
    return text.strip().title(), 0, "ML"

def get_game_result(identifier, line, type_, scores):
    for game in scores:
        if not game['completed']: continue
        h_team, a_team = game['home_team'], game['away_team']
        
        # Fuzzy Match
        identifier_clean = identifier.replace("Pick:", "").strip()
        if identifier_clean.lower() not in h_team.lower() and identifier_clean.lower() not in a_team.lower():
            continue 
            
        # Get Scores
        scores_list = game['scores']
        def get_score(name):
            for s in scores_list:
                if s['name'] == name: return int(s['score'])
            return 0

        h_score, a_score = get_score(h_team), get_score(a_team)
        
        # LOGIC
        if type_ in ["OVER", "UNDER"]:
            total = h_score + a_score
            if type_ == "OVER": return "WIN" if total > line else "LOSS"
            if type_ == "UNDER": return "WIN" if total < line else "LOSS"
            return "PUSH"

        # Identify My Team vs Opponent
        if identifier_clean.lower() in h_team.lower():
            my_score, opp_score = h_score, a_score
        else:
            my_score, opp_score = a_score, h_score

        if type_ == "ML":
            if my_score > opp_score: return "WIN"
            if my_score < opp_score: return "LOSS"
            return "PUSH"
            
        elif type_ == "SPREAD":
            diff = (my_score + line) - opp_score
            if diff > 0: return "WIN"
            if diff < 0: return "LOSS"
            return "PUSH"

    return "UNKNOWN"

# --- EXECUTION ---
if __name__ == "__main__":
    if not os.path.exists(PICKS_FILE): 
        print("No picks file found.")
        exit()
    
    with open(PICKS_FILE, "r") as f:
        picks_data = json.load(f)

    history = load_history()
    
    if history.get("updated_date") == picks_data["date"]:
        print(f"Already updated for date: {picks_data['date']}")
        exit()

    print(f"Checking NCAAB results for: {picks_data['date']}")
    print("Fetching scores from API...")
    
    # Note: Confirmed endpoint is 'basketball_ncaab'
    url = f"https://api.the-odds-api.com/v4/sports/basketball_ncaab/scores/?daysFrom=3&apiKey={ODDS_API_KEY}"
    response = requests.get(url)
    scores_data = response.json()

    # Update Lock
    id_l, line_l, type_l = parse_pick_text(picks_data["lock"])
    if id_l:
        res = get_game_result(id_l, line_l, type_l, scores_data)
        print(f"🔒 LOCK ({id_l}): {res}")  # <--- The Bot Speaks!
        if res == "WIN": history["lock"]["wins"] += 1
        elif res == "LOSS": history["lock"]["losses"] += 1
        elif res == "PUSH": history["lock"]["pushes"] += 1

    # Update Value
    id_v, line_v, type_v = parse_pick_text(picks_data["value"])
    if id_v:
        res = get_game_result(id_v, line_v, type_v, scores_data)
        print(f"🐕 VALUE ({id_v}): {res}") # <--- The Bot Speaks!
        if res == "WIN": history["value"]["wins"] += 1
        elif res == "LOSS": history["value"]["losses"] += 1
        elif res == "PUSH": history["value"]["pushes"] += 1

    history["updated_date"] = picks_data["date"]
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)
    
    print("NCAAB Verification Complete. History Updated.")
