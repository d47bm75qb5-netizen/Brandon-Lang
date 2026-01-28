import os
import json
import requests
import google.generativeai as genai
from datetime import datetime, timedelta, timezone

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

HISTORY_FILE = 'history.json'
PICKS_FILE = 'picks.json'

def get_scores(sport_key="basketball_nba"):
    # Fetch completed game scores for the last 1 days
    url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores'
    params = {
        'apiKey': ODDS_API_KEY,
        'daysFrom': 1, # Look at games from the last 24 hours
        'dateFormat': 'iso'
    }
    try:
        response = requests.get(url, params=params)
        return response.json()
    except:
        return []

def grade_picks():
    # 1. Load Today's Picks
    if not os.path.exists(PICKS_FILE):
        print("No picks file found to grade.")
        return

    with open(PICKS_FILE, 'r') as f:
        daily_pick = json.load(f)

    # 2. Get Actual Scores
    # Note: Defaults to NBA, but you can add logic to check NFL if current date is a Sunday
    scores_data = get_scores("basketball_nba") 
    
    # 3. Ask AI to Grade the Result
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are the Official Scorer. Grade these betting picks based on the final scores.
    
    The Picks:
    - Lock of the Day: {daily_pick.get('lock_of_the_day')}
    - Value Play: {daily_pick.get('value_play')}
    
    The Final Scores Data:
    {json.dumps(scores_data)}
    
    INSTRUCTIONS:
    - Compare the pick (Spread, Moneyline, Total, or Prop) against the final score.
    - Return a JSON object ONLY. No markdown.
    - Result options: "WIN", "LOSS", "PUSH", "PENDING" (if game isn't over).
    
    JSON FORMAT:
    {{
        "lock_result": "WIN",
        "value_result": "LOSS"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        grading = json.loads(response.text.replace('```json', '').replace('```', ''))
        
        # 4. Update History
        new_record = {
            "date": daily_pick.get("date"),
            "lock_pick": daily_pick.get("lock_of_the_day"),
            "lock_result": grading.get("lock_result", "PENDING"),
            "value_pick": daily_pick.get("value_play"),
            "value_result": grading.get("value_result", "PENDING")
        }
        
        # Load existing history
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        
        # Append today's result
        history.insert(0, new_record) # Add to top of list
        
        # Save back
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=4)
            
        print("Grading Complete. History updated.")
        
    except Exception as e:
        print(f"Error grading picks: {e}")

if __name__ == "__main__":
    grade_picks()
