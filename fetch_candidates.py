import os
import requests
import warnings
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from the local .env file
load_dotenv()

# Suppress the macOS LibreSSL warning
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

API_KEY = os.getenv("FEC_API_KEY", "DEMO_KEY") 
BASE_URL = "https://api.open.fec.gov/v1"

def get_official_qualified_names():
    file_path = "dos_qualified.txt"
    if not os.path.exists(file_path):
        print(f"\n[!] Warning: Could not find '{file_path}' in your folder.")
        return None
        
    try:
        dos_df = pd.read_csv(file_path, sep='\t', encoding='utf-8', dtype=str)
        dos_df['OfficeDesc'] = dos_df['OfficeDesc'].fillna('').str.strip()
        
        fed_dos = dos_df[dos_df['OfficeDesc'].str.contains('United States Senator|United States Representative', case=False, na=False)].copy()
        
        # Find the state's district column dynamically
        district_col = next((col for col in fed_dos.columns if col.lower() in ['juris1num', 'district', 'districtnum']), None)
        
        qualified_candidates = []
        for _, row in fed_dos.iterrows():
            last_name = str(row.get('NameLast', '')).strip().lower()
            first_name = str(row.get('NameFirst', '')).strip().lower()
            
            # Extract the official state district
            dos_district = "Statewide"
            if 'Senator' not in str(row.get('OfficeDesc', '')):
                if district_col and pd.notna(row[district_col]):
                    dos_district = str(row[district_col]).strip()
            
            if last_name: 
                qualified_candidates.append({
                    'last_name': last_name,
                    'first_name': first_name,
                    'raw_name': f"{last_name.upper()}, {first_name.upper()}",
                    'dos_district': dos_district
                })
                
        print(f" -> Found {len(qualified_candidates)} officially filed federal candidates in local DOS file.")
        return qualified_candidates
        
    except Exception as e:
        print(f"[!] Error reading DOS file: {e}")
        return None

def clean_name_string(name):
    name = str(name).lower().replace('.', '').replace(',', '').replace("'", "").replace('"', "")
    suffixes = [' jr', ' sr', ' ii', ' iii', ' iv', ' md']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()

def fetch_fl_2026_candidates(api_key):
    if api_key == "DEMO_KEY":
        print("DEBUG: Python is using the fallback 'DEMO_KEY'.")
    else:
        print(f"DEBUG: Success! Using key starting with: {api_key[:5]}...")

    qualified_list = get_official_qualified_names()

    print("Fetching Florida 2026 federal candidates from FEC...")
    endpoint = f"{BASE_URL}/candidates/"
    
    params = {
        "api_key": api_key,
        "state": "FL",
        "cycle": "2026",
        "election_year": "2026",
        "per_page": 100,
        "sort": "name"
    }
    
    all_candidates = []
    
    while True:
        current_page = params.get('page', 1)
        print(f" -> Pinging API for page {current_page}...")
        
        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"\n[!] Network or rate error occurred: {e}")
            break
            
        data = response.json()
        results = data.get('results', [])
        all_candidates.extend(results)
        
        pagination = data.get('pagination', {})
        if pagination.get('pages') and current_page < pagination.get('pages'):
            params['page'] = current_page + 1
        else:
            break
            
    df = pd.DataFrame(all_candidates)
    
    if not df.empty:
        ideal_columns = [
            'candidate_id', 'name', 'office_full', 'party_full', 
            'district', 'incumbent_challenge_full', 'principal_committees', 
            'principal_committee_ids'
        ]
        existing_columns = [col for col in ideal_columns if col in df.columns]
        df = df[existing_columns]
        
        if qualified_list is not None and len(qualified_list) > 0:
            def get_official_district(fec_name):
                fec_name_clean = str(fec_name).lower().strip()
                parts = fec_name_clean.split(',')
                fec_last = clean_name_string(parts[0])
                fec_first = clean_name_string(parts[1]) if len(parts) > 1 else ""

                for q_candidate in qualified_list:
                    q_last = clean_name_string(q_candidate['last_name'])
                    q_first = clean_name_string(q_candidate['first_name'])
                    
                    if fec_last == q_last:
                        if fec_first and q_first:
                            q_first_parts = q_first.split()
                            fec_first_parts = fec_first.split()
                            
                            for q_part in q_first_parts:
                                for f_part in fec_first_parts:
                                    if len(q_part) > 2 and (q_part in f_part or f_part in q_part):
                                        return q_candidate['dos_district']
                                        
                            if (q_first in fec_first) or (fec_first in q_first):
                                return q_candidate['dos_district']
                        else:
                            return q_candidate['dos_district']
                return None

            print("Filtering FEC results and injecting authoritative DOS district mapping...")
            
            df['dos_district'] = df['name'].apply(get_official_district)
            dropped = df[df['dos_district'].isnull()]['name'].tolist()
            if dropped:
                print(f" -> Dropped {len(dropped)} historical/unfiled FEC accounts not on the DOS list.")
                
            df = df[df['dos_district'].notnull()].copy()

        # Load the dynamic county crosswalk built from the state's redistricting text file
        crosswalk_file = 'district_counties.csv'
        FL_COUNTIES = {}
        if os.path.exists(crosswalk_file):
            cw_df = pd.read_csv(crosswalk_file, dtype=str)
            FL_COUNTIES = dict(zip(cw_df['district_num'], cw_df['county_list']))
        else:
            print(f"\n[!] Warning: '{crosswalk_file}' not found. Counties will not display.")
            print("    Run build_crosswalk.py first to generate the county map.")

        if 'office_full' in df.columns:
            def format_office(row):
                office = str(row.get('office_full', ''))
                district = str(row.get('dos_district', row.get('district', '')))
                
                if office == 'Senate' or district == 'Statewide':
                    return "Senate|Statewide (All 67 Counties)"
                
                if district and district not in ['00', '0', 'None', 'nan', '']:
                    try:
                        dist_num = str(int(float(district)))
                        counties = FL_COUNTIES.get(dist_num, "Multiple Counties")
                        return f"House (District {dist_num})|{counties}"
                    except ValueError:
                        return office
                return office
            
            df['office_full'] = df.apply(format_office, axis=1)
            df = df.drop(columns=['district', 'dos_district'], errors='ignore')
            
        print(f"\nSuccessfully structured {len(df)} QUALIFIED candidates into our dataset using authoritative DOS districts.")
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