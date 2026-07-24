import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

def build_automated_crosswalk():
    candidate_file = "fl_2026_state_tracker_latest.csv"
    output_file = "state_pc_crosswalk.csv"
    
    if not os.path.exists(candidate_file):
        print(f"[!] Cannot find {candidate_file}. Please run your main roster scripts first.")
        return

    df = pd.read_csv(candidate_file, dtype=str)
    print(f"Loaded {len(df)} state candidates. Scanning Florida DOS for linked Political Committees...")

    pc_matches = []
    
    # State endpoint for searching committees by name
    search_url = "https://dos.elections.myflorida.com/committees/ComMain.asp"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SunSentinel Election Tracker DataBot'
    }

    for idx, row in df.iterrows():
        cand_id = row['candidate_id']
        full_name = row['name']
        
        # Extract the last name to use as a search query
        # Handles "Duda Buckley" or names with suffixes cleanly
        name_parts = full_name.replace(",", "").split()
        last_name = name_parts[-1] if name_parts else ""
        
        if not last_name or len(last_name) < 3:
            continue
            
        print(f"Searching for committees linked to: {full_name} (Query: '{last_name}')...")
        
        # Form payload data that mimics the state's search form
        payload = {
            'comName': last_name,
            'comStatus': 'A',  # Only find 'Active' committees
            'comType': 'A',    # Search all types
            'Search': 'Search'
        }
        
        try:
            time.sleep(0.5)  # Don't anger the Tallahassee server
            response = requests.post(search_url, data=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link['href']
                    if 'account=' in href.lower():
                        # Extract the PC ID from the link string
                        pc_id = href.split('account=')[-1].strip()
                        pc_name = link.get_text(strip=True)
                        
                        # Match verification step: Check if the candidate's first name 
                        # or last name appears inside the scraped committee title string
                        first_name = name_parts[0].lower() if name_parts else ""
                        clean_pc_title = pc_name.lower()
                        
                        if last_name.lower() in clean_pc_title:
                            # High probability match! Log it.
                            pc_matches.append({
                                'candidate_id': cand_id,
                                'candidate_name': full_name,
                                'pc_acct_num': pc_id,
                                'pc_name': pc_name
                            })
                            print(f"   [MATCH FOUND]: '{pc_name}' (ID: {pc_id})")
                            
        except Exception as e:
            print(f"   [Error searching for {last_name}]: {e}")
            pass

    if pc_matches:
        match_df = pd.DataFrame(pc_matches)
        # Drop absolute duplicates
        match_df = match_df.drop_duplicates(subset=['candidate_id', 'pc_acct_num'])
        match_df.to_csv(output_file, index=False)
        print(f"\nSUCCESS: Automated crosswalk generated! File saved to {output_file}")
        print("Review the file to quickly remove any false-positive name collisions before scraping.")
    else:
        print("\nNo matching committees discovered automatically.")

if __name__ == "__main__":
    build_automated_crosswalk()