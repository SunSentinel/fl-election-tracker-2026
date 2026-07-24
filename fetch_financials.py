import os
import time
import glob
import warnings
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

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
    print(f"Fetching financial totals from the FEC using UPGRADED API Key: {api_key[:5]}...")
    
    session = requests.Session()
    retries = Retry(
        total=3,                
        backoff_factor=0.5,     
        status_forcelist=[500, 502, 503, 504], 
        raise_on_status=False
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
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
            time.sleep(0.6) 
            response = session.get(endpoint, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                totals = results[0]
                
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
                    'cash_on_hand_end_period': coh,
                    'pac_money': totals.get('other_political_committee_contributions', 0.0),
                    'loans': totals.get('loans', 0.0)
                })
            else:
                financial_data.append({
                    'candidate_id': candidate_id,
                    'receipts': 0.0,
                    'disbursements': 0.0,
                    'cash_on_hand_end_period': 0.0,
                    'pac_money': 0.0,
                    'loans': 0.0
                })
                
        except requests.exceptions.RequestException as e:
            print(f"    [!] Failed to fetch {candidate_name} after retries: {e}. Recording placeholder data...")
            financial_data.append({
                'candidate_id': candidate_id,
                'receipts': 0.0,
                'disbursements': 0.0,
                'cash_on_hand_end_period': 0.0,
                'pac_money': 0.0,
                'loans': 0.0
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
            
            # --- DE-DUPLICATION ENGINE ---
            print("\nScanning dataset for candidate entry duplicates...")
            initial_count = len(merged_df)
            
            # Standardize names to check for spelling variants (e.g., catching Carla A vs Carla Arlene)
            # We take the first two words of the name (usually LASTNAME, FIRSTNAME)
            merged_df['_name_clean'] = merged_df['name'].str.lower().str.replace(r'[^\w\s,]', '', regex=True)
            merged_df['_name_key'] = merged_df['_name_clean'].apply(lambda x: ' '.join(x.split()[:2]))
            
            # Sort by total receipts descending so if we drop a row, we keep the one holding actual financial records
            merged_df = merged_df.sort_values(by='receipts', ascending=False)
            
            # Drop duplicates based on Name Key AND Office
            merged_df = merged_df.drop_duplicates(subset=['_name_key', 'office_full'], keep='first')
            
            # Drop duplicates based on principal committee ID if available (so two IDs pointing to the same bank account merge)
            if 'principal_committee_ids' in merged_df.columns:
                merged_df = merged_df.dropna(subset=['principal_committee_ids']).drop_duplicates(subset=['principal_committee_ids', 'office_full'], keep='first').combine_first(merged_df)
            
            # Clean up temporary matching columns
            merged_df = merged_df.drop(columns=['_name_clean', '_name_key'], errors='ignore')
            
            final_count = len(merged_df)
            print(f" -> Removed {initial_count - final_count} duplicate FEC candidate listings from tracking tables.")
            # ------------------------------
            
            export_filename = "fl_2026_tracker_master_latest.csv"
            merged_df.to_csv(export_filename, index=False)
            print(f"SUCCESS! Clean master tracker dataset exported to {export_filename}")
        else:
            print("\nNo financial data could be retrieved.")
            
    except Exception as e:
        print(f"An error occurred: {e}")