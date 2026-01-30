import os
import requests
import json
import google.generativeai as genai
from datetime import datetime
from zoneinfo import ZoneInfo  # <--- NEW: Import Timezone support

# --- CONFIGURATION ---
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

def get_ncaab_odds():
    """Fetches upcoming NCAAB odds from The Odds API."""
    url = f"https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds/?regions=us&markets=spreads&oddsFormat=american&apiKey={ODDS_API_KEY}"
    try:
        print(f"📡 Connecting to Odds API...")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Odds Fetched: {len(data)} games found.")
        return data
    except Exception as e:
        print(f"❌ Error fetching odds: {e}")
        return []

def format_games_with_context(games_data):
    """
    Extracts lines and formats them for the AI.
    """
    game_lines = []
    
    # Process top 25 games to give us a good selection
    for game in games_data[:25]: 
        home = game.get('home_team')
        away = game.get('away_team')
        
        # Extract Spread
        spread_text = "No Spread"
        try:
            bookmakers = game.get('bookmakers', [])
            if bookmakers:
                markets = bookmakers[0].get('markets', [])
                if markets:
                    outcomes = markets[0].get('outcomes', [])
                    # Find spread
                    p1 = outcomes[0]
                    p2 = outcomes[1]
                    spread_text = f"{p1['name']} ({p1['point']}) vs {p2['name']} ({p2['point']})"
        except:
            continue

        if spread_text != "No Spread":
            line = f"MATCHUP: {away} @ {home} | LINE: {spread_text}"
            game_lines.append(line)

    return "\n".join(game_lines)

def generate_picks(formatted_games_text):
    """Sends Clean Lines + Stat Instructions to Gemini."""
    
    # --- TIMEZONE FIX ---
    # Force the date to be US Eastern Time, not UTC
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    if not formatted_games_text:
        return {
            "date": today,
            "lock": "No Games Found",
            "value": "No Games Found",
            "analysis": "No odds available. Season might be paused."
        }

    prompt = f"""
    You are a sharp Vegas sports bettor named 'Brandon Lang'.
    Today is {today}.
    
    Here are the OFFICIAL lines for today's NCAA Basketball games:
    {formatted_games_text}

    YOUR MISSION:
    1.  **Analyze the Matchups:** Use your internal knowledge base to recall the current season performance for these teams.
    2.  **Pick Winners:** -   **LOCK:** Find the mismatch. (e.g., A top team playing a struggling team).
        -   **VALUE:** Find the underdog who can score.
    
    CRITICAL RULES:
    -   You MUST select the spread exactly as written in the list above.
    -   Do NOT invent lines.

    OUTPUT JSON ONLY:
    {{
        "date": "{today}",
        "lock": "Team Name (Spread)",
        "value": "Team Name (Spread)",
        "analysis": "Your detailed breakdown here..."
    }}
    """

    try:
        print("🧠 Sending matchups to Gemini 2.5...")
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response = model.generate_content(prompt)
        
        text = response.text.strip()
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "")
        elif text.startswith("```"):
            text = text.replace("```", "")
            
        return json.loads(text)
    except Exception as e:
        print(f"❌ Error generating picks: {e}")
        return {
            "date": today,
            "lock": "Error",
            "value": "Error",
            "analysis": f"AI Error: {e}"
        }

if __name__ == "__main__":
    print("🚀 Starting NCAAB Pick Generator...")
    
    # 1. Get Odds
    raw_odds = get_ncaab_odds()
    
    # 2. Format
    clean_lines = format_games_with_context(raw_odds)
    print("------- VALID LINES -------")
    print(clean_lines)
    print("---------------------------")

    # 3. Generate Picks
    picks = generate_picks(clean_lines)
    
    # 4. Save
    output_file = "ncaab_picks.json"
    with open(output_file, "w") as f:
        json.dump(picks, f, indent=4)
    
    print(f"✅ Picks saved to {output_file}")
