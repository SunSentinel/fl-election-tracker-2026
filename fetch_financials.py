import os
import time
import glob
import warnings
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

# Pull the secure key from the environment. Fall back to DEMO_KEY if not found.
API_KEY = os.getenv("FEC_API_KEY", "DEMO_KEY")
BASE_URL = "https://api.open.fec.gov/v1"

HEADERS = {
    "User-Agent": "Newsroom Campaign Finance Tracker 1.0 (Contact: data@newsroom.com)"
}

def get_latest_candidate_file():
    list_of_files = glob.glob('fl_2026_candidates_*.csv')
    if not list_of_files:
        raise FileNotFoundError("No candidate CSV found. Run fetch_candidates.py first.")
    return max(list_of_files, key=os.path.getctime)

def fetch_financial_totals(api_key, candidate_df):
    print(f"Fetching financial totals from the FEC using API Key: {api_key[:5]}...")
    
    financial_data = []
    
    # Process ALL candidates found in our CSV roster
    for index, row in candidate_df.iterrows():
        candidate_id = row['candidate_id']
        candidate_name = row['name']
        
        print(f" -> [{index + 1}/{len(candidate_df)}] Fetching totals for: {candidate_name}")
        endpoint = f"{BASE_URL}/candidate/{candidate_id}/totals/"
        
        params = {
            "api_key": api_key,
            "cycle": "2026"  # Updated this to correctly grab the 2026 cycle
        }
        
        try:
            # 1-second pause to easily stay under your standard key limit (1,000 calls/hour)
            time.sleep(1) 
            
            # 5 seconds lets us skip past intermittent server lag instantly
            response = requests.get(endpoint, headers=HEADERS, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                totals = results[0]
                
                # DIAGNOSTIC: Print the raw keys for the very first candidate
                if index == 0:
                    print(f"\n[DEBUG] Raw FEC Totals Keys for {candidate_name}:")
                    print(list(totals.keys()))
                    print("\n")
                
                # Check for all possible FEC cash-on-hand variations to bypass the $0 fallback trap
                coh = (
                    totals.get('cash_on_hand_cop') or 
                    totals.get('cash_on_hand') or 
                    totals.get('cash_on_hand_end_period') or 
                    0.0
                )
                
                financial_data.append({
                    'candidate_id': candidate_id,
                    'receipts': totals.get('receipts', 0.0),
                    'disbursements': totals.get('disbursements', 0.0),
                    'cash_on_hand_end_period': coh 
                })
            else:
                # If they haven't filed 2026 numbers yet, we record zeros so the table isn't blank
                financial_data.append({
                    'candidate_id': candidate_id,
                    'receipts': 0.0,
                    'disbursements': 0.0,
                    'cash_on_hand_end_period': 0.0
                })
                
        except requests.exceptions.RequestException as e:
            # If the request times out or errors, log it, record baseline zeros, and keep moving
            print(f"    [!] Failed to fetch {candidate_name}: {e}. Recording placeholder data and skipping...")
            financial_data.append({
                'candidate_id': candidate_id,
                'receipts': 0.0,
                'disbursements': 0.0,
                'cash_on_hand_end_period': 0.0
            })
            continue

    return pd.DataFrame(financial_data)

if __name__ == "__main__":
    try:
        latest_csv = get_latest_candidate_file()
        print(f"Loading candidate roster from: {latest_csv}")
        candidates_df = pd.read_csv(latest_csv)
        
        financials_df = fetch_financial_totals(API_KEY, candidates_df)
        
        if not financials_df.empty:
            # Structural merge combining candidate metadata with their financial rows
            merged_df = pd.merge(candidates_df, financials_df, on='candidate_id', how='inner')
            
            timestamp = datetime.now().strftime("%Y%m%d")
            export_filename = f"fl_2026_tracker_master_{timestamp}.csv"
            
            merged_df.to_csv(export_filename, index=False)
            print(f"\nSUCCESS! Master tracker dataset exported to {export_filename}")
        else:
            print("\nNo financial data could be retrieved.")
            
    except Exception as e:
        print(f"An error occurred: {e}")