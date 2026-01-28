import os
import json
import requests
import google.generativeai as genai

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

HISTORY_FILE = 'ncaab_history.json'
PICKS_FILE = 'ncaab_picks.json'

def get_scores():
    # Fetch completed NCAAB scores
    url = f'https://api.the-odds-api.com/v4/sports/basketball_ncaab/scores'
    params = {
        'apiKey': ODDS_API_KEY,
        'daysFrom': 1,
        'dateFormat': 'iso'
    }
    try:
        response = requests.get(url, params=params)
        return response.json()
    except:
        return []

def grade_picks():
    if not os.path.exists(PICKS_FILE): return

    with open(PICKS_FILE, 'r') as f:
        daily_pick = json.load(f)

    scores_data = get_scores()
    
    # ASK GEMINI TO GRADE
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are the Official Scorer. Grade these NCAAB picks.
    
    Picks:
    - Lock: {daily_pick.get('lock')}
    - Value: {daily_pick.get('value')}
    
    Scores:
    {json.dumps(scores_data)}
    
    Output JSON ONLY:
    {{ "lock_result": "WIN/LOSS", "value_result": "WIN/LOSS" }}
    """
    
    try:
        response = model.generate_content(prompt)
        grading = json.loads(response.text.replace('```json', '').replace('```', ''))
        
        new_record = {
            "date": daily_pick.get("date"),
            "lock_pick": daily_pick.get("lock"),
            "lock_result": grading.get("lock_result", "PENDING"),
            "value_pick": daily_pick.get("value"),
            "value_result": grading.get("value_result", "PENDING")
        }
        
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        
        history.insert(0, new_record)
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=4)
            
    except Exception as e:
        print(f"Error grading: {e}")

if __name__ == "__main__":
    grade_picks()
