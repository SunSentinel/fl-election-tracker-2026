import requests
import pandas as pd
import warnings
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Suppress the macOS LibreSSL warning
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

# Pull the real key securely, default to DEMO_KEY if missing
API_KEY = os.getenv("FEC_API_KEY", "DEMO_KEY") 
BASE_URL = "https://api.open.fec.gov/v1"

def fetch_fl_2026_candidates(api_key):
    if api_key == "DEMO_KEY":
        print("DEBUG: Python is using the fallback 'DEMO_KEY'. It cannot find your .env file!")
    else:
        print(f"DEBUG: Success! Python found your .env file. Using key starting with: {api_key[:5]}...")

    print("Fetching Florida 2026 federal candidates from FEC...")
    endpoint = f"{BASE_URL}/candidates/"
    
    params = {
        "api_key": api_key,
        "state": "FL",
        "cycle": "2026",
        "has_raised_funds": "true",
        "per_page": 100,
        "sort": "name"
    }
    
    all_candidates = []
    
    while True:
        current_page = params.get('page', 1)
        print(f" -> Pinging API for page {current_page}...")
        
        try:
            # BUMPED TIMEOUT TO 30 SECONDS
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            
        except requests.exceptions.ReadTimeout:
            print("\n[!] Error: The FEC API connection timed out. Server took too long to respond.")
            break
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print(f"\n[!] Error 429: Rate limit exceeded using key: {api_key[:5]}...")
            else:
                print(f"\n[!] HTTP Error: {e}")
            break
        except requests.exceptions.RequestException as e:
            print(f"\n[!] A network error occurred: {e}")
            break
            
        data = response.json()
        results = data.get('results', [])
        all_candidates.extend(results)
        
        print(f"    ...Found {len(results)} candidates on this page.")
        
        pagination = data.get('pagination', {})
        if pagination.get('pages') and current_page < pagination.get('pages'):
            params['page'] = current_page + 1
        else:
            break
            
    df = pd.DataFrame(all_candidates)
    
    if not df.empty:
        ideal_columns = [
            'candidate_id', 'name', 'office_full', 'party_full', 
            'incumbent_challenge_full', 'principal_committees', 
            'principal_committee_ids'
        ]
        existing_columns = [col for col in ideal_columns if col in df.columns]
        df = df[existing_columns]
        print(f"\nSuccessfully structured {len(df)} candidates into our dataset.")
    else:
        print("\nNo candidate data was retrieved.")
        
    return df

if __name__ == "__main__":
    fl_candidates_df = fetch_fl_2026_candidates(API_KEY)
    
    if not fl_candidates_df.empty:
        timestamp = datetime.now().strftime("%Y%m%d")
        export_filename = f"fl_2026_candidates_{timestamp}.csv"
        fl_candidates_df.to_csv(export_filename, index=False)
        print(f"Data exported to {export_filename}")