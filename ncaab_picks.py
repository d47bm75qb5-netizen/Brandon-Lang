import os
import requests
import json
import google.generativeai as genai
from datetime import datetime

# --- CONFIGURATION ---
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

def get_ncaab_odds():
    """Fetches upcoming NCAAB odds from The Odds API."""
    url = f"https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds/?regions=us&markets=h2h,spreads,totals&oddsFormat=american&apiKey={ODDS_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # DEBUG: Print first 3 games to logs to verify we have real lines
        print(f"✅ Fetched {len(data)} games.")
        if len(data) > 0:
            print("Sample Game 1:", json.dumps(data[0], indent=2))
            
        return data
    except Exception as e:
        print(f"❌ Error fetching odds: {e}")
        return []

def generate_picks(odds_data):
    """Sends odds to Gemini to generate the picks."""
    if not odds_data:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "lock": "No Games Found",
            "value": "No Games Found",
            "analysis": "Could not fetch odds from API."
        }

    # Prepare the prompt
    today = datetime.now().strftime("%Y-%m-%d")
    
    # We limit the data passed to the LLM to save tokens and confusion
    # Only sending the first 15 games to ensure we get the best lines (usually ranked teams)
    games_text = json.dumps(odds_data[:20], indent=2)

    prompt = f"""
    You are a professional Vegas sports bettor named 'Brandon Lang'.
    Today is {today}.
    
    Here are the betting lines for today's NCAA College Basketball games:
    {games_text}

    YOUR TASK:
    1. Analyze these matchups. Look for sharp money, mismatches, or trap lines.
    2. Pick ONE "LOCK OF THE DAY" (Your most confident bet).
    3. Pick ONE "VALUE PLAY" (An underdog or great odds play).
    4. Write a short, punchy, arrogant breakdown of why you love these picks.

    CRITICAL RULES:
    - You MUST verify that the spread/line you pick actually exists in the data provided. Do not make up numbers.
    - If a team is -2000 moneyline, do NOT pick them as a value play.
    - Output ONLY valid JSON in exactly this format:
    {{
        "date": "{today}",
        "lock": "Team Name (Spread or ML)",
        "value": "Team Name (Spread or ML)",
        "analysis": "Your analysis here..."
    }}
    """

    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        
        # Clean the response to ensure it's pure JSON
        text = response.text.strip()
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "")
        
        return json.loads(text)
    except Exception as e:
        print(f"❌ Error generating picks: {e}")
        return {
            "date": today,
            "lock": "Error",
            "value": "Error",
            "analysis": "The AI brain malfunctioned. Please check logs."
        }

if __name__ == "__main__":
    print("🚀 Starting NCAAB Pick Generator...")
    
    # 1. Get Odds
    odds = get_ncaab_odds()
    
    # 2. Generate Picks
    picks = generate_picks(odds)
    
    # 3. Save to File
    output_file = "ncaab_picks.json"
    with open(output_file, "w") as f:
        json.dump(picks, f, indent=4)
    
    print(f"✅ Picks saved to {output_file}")
    print("Lock:", picks.get("lock"))
    print("Value:", picks.get("value"))
