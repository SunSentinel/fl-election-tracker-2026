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
    
    for index, row in candidate_df.iterrows():
        candidate_id = row['candidate_id']
        candidate_name = row['name']
        
        print(f" -> [{index + 1}/{len(candidate_df)}] Fetching totals for: {candidate_name}")
        endpoint = f"{BASE_URL}/candidate/{candidate_id}/totals/"
        
        params = {
            "api_key": api_key,
            "cycle": "2026"  
        }
        
        try:
            # Pausing for 4 seconds keeps us safely at ~15 requests per minute (900/hour),
            # permanently keeping us under the FEC's 1,000 requests/hour rate limit ceiling.
            time.sleep(4) 
            
            response = requests.get(endpoint, headers=HEADERS, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                totals = results[0]
                
                # Bypassing the $0 fallback by targeting the correct verified key
                coh = (
                    totals.get('last_cash_on_hand_end_period') or 
                    totals.get('cash_on_hand_cop') or 
                    totals.get('cash_on_hand') or 
                    0.0
                )
                
                financial_data.append({
                    'candidate_id': candidate_id,
                    'receipts': totals.get('receipts', 0.0),
                    'disbursements': totals.get('disbursements', 0.0),
                    'cash_on_hand_end_period': coh 
                })
            else:
                financial_data.append({
                    'candidate_id': candidate_id,
                    'receipts': 0.0,
                    'disbursements': 0.0,
                    'cash_on_hand_end_period': 0.0
                })
                
        except requests.exceptions.RequestException as e:
            print(f"    [!] Failed to fetch {candidate_name}: {e}. Recording placeholder data...")
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
            merged_df = pd.merge(candidates_df, financials_df, on='candidate_id', how='inner')
            
            # Exporting to a clean, standardized latest filename format
            export_filename = "fl_2026_tracker_master_latest.csv"
            merged_df.to_csv(export_filename, index=False)
            print(f"\nSUCCESS! Master tracker dataset exported to {export_filename}")
        else:
            print("\nNo financial data could be retrieved.")
            
    except Exception as e:
        print(f"An error occurred: {e}")