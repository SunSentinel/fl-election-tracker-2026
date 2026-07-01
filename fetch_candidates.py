import requests
import pandas as pd
import warnings
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from the local .env file
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
            # 30-second timeout to give sluggish servers more time
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
        # Add 'district' to our list of ideal columns to extract from the JSON
        ideal_columns = [
            'candidate_id', 'name', 'office_full', 'party_full', 
            'district', 'incumbent_challenge_full', 'principal_committees', 
            'principal_committee_ids'
        ]
        existing_columns = [col for col in ideal_columns if col in df.columns]
        df = df[existing_columns]
        
        # Enacted May 2026 Special Session Mid-Decade Map (Plan EOGPCRP2026 / HB 1-D)
        FL_COUNTIES = {
            "1": "Escambia, Santa Rosa, Okaloosa, Walton",
            "2": "Bay, Calhoun, Franklin, Gadsden, Gulf, Holmes, Jackson, Jefferson, Lafayette, Leon, Liberty, Madison, Taylor, Wakulla, Washington",
            "3": "Alachua, Baker, Bradford, Columbia, Dixie, Gilchrist, Levy, Marion, Suwannee, Union",
            "4": "Clay, Duval, Nassau",
            "5": "Duval, St. Johns",
            "6": "Flagler, Lake, Marion, Putnam, St. Johns, Volusia",
            "7": "Seminole, Volusia",
            "8": "Brevard, Indian River, Orange",
            "9": "Orange, Osceola, Polk, Indian River, Okeechobee, Highlands, Glades",
            "10": "Orange",
            "11": "Lake, Orange, Polk, Sumter",
            "12": "Citrus, Hernando, Pasco",
            "13": "Pinellas",
            "14": "Hillsborough, Pinellas",
            "15": "Hillsborough, Pasco, Polk",
            "16": "Hillsborough, Manatee",
            "17": "Charlotte, Lee, Sarasota",
            "18": "Collier, DeSoto, Glades, Hardee, Hendry, Highlands, Okeechobee, Polk",
            "19": "Collier, Lee",
            "20": "Broward, Palm Beach",
            "21": "Martin, Palm Beach, St. Lucie",
            "22": "Broward, Palm Beach",
            "23": "Broward, Palm Beach",
            "24": "Broward, Miami-Dade",
            "25": "Broward, Miami-Dade",
            "26": "Collier, Miami-Dade, Monroe",
            "27": "Miami-Dade",
            "28": "Miami-Dade, Monroe"
        }
        
        if 'district' in df.columns and 'office_full' in df.columns:
            def format_office(row):
                office = str(row.get('office_full', ''))
                district = str(row.get('district', ''))
                
                if office == 'Senate':
                    return "Senate|Statewide (All 67 Counties)"
                
                if office == 'House' and district and district not in ['00', '0', 'None', 'nan']:
                    try:
                        dist_num = str(int(float(district)))
                        counties = FL_COUNTIES.get(dist_num, "Multiple Counties")
                        # We use a pipe "|" to split the office string cleanly on the front end
                        return f"House (District {dist_num})|{counties}"
                    except ValueError:
                        return office
                return office
            
            # Apply the formatting rule to every row
            df['office_full'] = df.apply(format_office, axis=1)
            
            # Drop the raw district column so we don't clutter the final CSV
            df = df.drop(columns=['district'])
            
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