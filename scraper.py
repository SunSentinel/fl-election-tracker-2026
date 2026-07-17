import os
import requests
import json
import time
import csv
import warnings
from io import StringIO
from datetime import datetime
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Suppress the macOS LibreSSL warning
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

# ==============================================================================
# SOUTH FLORIDA REDISTRICTING CONFIG (AUDITED FOR CURRENT MAP)
# ==============================================================================
SOUTH_FLORIDA_MAP = {
    # District 18 removed (Central Florida)
    # District 19 removed per request (Collier, Lee)
    "USC 020": {"office": "House District 20", "counties": "Palm Beach, Broward"},
    "USC 021": {"office": "House District 21", "counties": "St. Lucie, Martin, Palm Beach"},
    "USC 022": {"office": "House District 22", "counties": "Palm Beach"},
    "USC 023": {"office": "House District 23", "counties": "Palm Beach, Broward"},
    "USC 024": {"office": "House District 24", "counties": "Miami-Dade, Broward"},
    "USC 025": {"office": "House District 25", "counties": "Broward"},
    "USC 026": {"office": "House District 26", "counties": "Miami-Dade, Collier"},
    "USC 027": {"office": "House District 27", "counties": "Miami-Dade"},
    "USC 028": {"office": "House District 28", "counties": "Miami-Dade, Monroe"},
    "USS 001": {"office": "U.S. Senate", "counties": "Statewide"}
}

API_KEY = os.getenv("FEC_API_KEY", "l0hX7OVEFfgsSxPWOggS3AQ8xy6D3bcixJ8rifcJ")
CYCLE = "2026"
BASE_URL = "https://api.open.fec.gov/v1"

# ==============================================================================
# HTTP SESSION SETUP (Connection Pooling & Retries)
# ==============================================================================
fec_session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
fec_session.mount('https://', HTTPAdapter(max_retries=retries))

def clean_name_string(name):
    name = str(name).lower().replace('.', '').replace(',', '').replace("'", "").replace('"', "")
    suffixes = [' jr', ' sr', ' ii', ' iii', ' iv', ' md']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()

def parse_csv_content(decoded_content):
    """Core parser logic for the state roster."""
    reader = csv.DictReader(StringIO(decoded_content), delimiter='\t')
    qualified_candidates = []
    
    def get_val(row, *keywords):
        for key, val in row.items():
            if key and any(k.lower() in key.lower() for k in keywords): 
                return str(val).strip()
        return ""

    for row in reader:
        status = get_val(row, 'status')
        office_desc = get_val(row, 'officedesc', 'office desc', 'office description')
        name_last = get_val(row, 'namelast', 'last name')
        name_first = get_val(row, 'namefirst', 'first name')
        party = get_val(row, 'party')
        juris = get_val(row, 'juris1num', 'district', 'districtnum')
        
        is_valid_contender = True
        if status:
            s_low = status.lower()
            if 'withdrawn' in s_low or 'wdd' in s_low or 'defeated' in s_low or 'def' in s_low:
                is_valid_contender = False
                
        if not is_valid_contender:
            continue

        search_code = None
        
        if "united states senator" in office_desc.lower():
            search_code = "USS 001"
        elif "united states representative" in office_desc.lower():
            try:
                dist_num = int(juris)
                search_code = f"USC {dist_num:03d}" 
            except ValueError:
                pass 
                
        if search_code and search_code in SOUTH_FLORIDA_MAP:
            mapped = SOUTH_FLORIDA_MAP[search_code]
            if name_last:
                qualified_candidates.append({
                    'last_name': name_last.lower(),
                    'first_name': name_first.lower(),
                    'clean_display_name': f"{name_last.upper()}, {name_first.upper()}",
                    'party_full': party,
                    'office_full': mapped["office"],
                    'counties': mapped["counties"]
                })
                
    return qualified_candidates

def get_state_roster():
    """Reads from authoritative local file 'dos_qualified.txt'."""
    print("📥 Qualification period closed. Reading from authoritative local file 'dos_qualified.txt'...")
    file_path = "dos_qualified.txt"
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                decoded_content = f.read()
            qualified_candidates = parse_csv_content(decoded_content)
            print(f" -> Found {len(qualified_candidates)} officially qualified South Florida federal candidates.")
            return qualified_candidates
        except Exception as e:
            print(f"❌ Critical Error parsing local file: {e}")
            return []
    else:
        print(f"❌ Critical Error: '{file_path}' was not found in the directory.")
        return []

def fetch_fec_bulk_pool():
    print("📥 Extracting Florida 2026 master data matrix from FEC...")
    endpoint = f"{BASE_URL}/candidates/"
    params = {"api_key": API_KEY, "state": "FL", "cycle": "2026", "election_year": "2026", "per_page": 100}
    
    all_candidates = []
    while True:
        current_page = params.get('page', 1)
        try:
            response = fec_session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            all_candidates.extend(data.get('results', []))
            
            pagination = data.get('pagination', {})
            if pagination.get('pages') and current_page < pagination.get('pages'):
                params['page'] = current_page + 1
            else:
                break
        except Exception as e:
            print(f"❌ API compilation batch exception: {e}")
            break
    return all_candidates

def main():
    print(f"[{datetime.now()}] Initializing clean committee data matrix...")
    state_roster = get_state_roster()
    
    if not state_roster:
        print("🚨 Run halted: State authoritative master block is empty.")
        return
        
    fec_pool = fetch_fec_bulk_pool()
    master_output = []

    # === MANUAL FEC CROSSWALK OVERRIDES ===
    MANUAL_OVERRIDES = {
        "NIXON, ANGIE": {"last": "nixon", "first": "angela"},
        "KAUFMAN, JOSEPH": {"last": "kaufman", "first": "joe"},
        "OBERWEIS, JIM": {"last": "oberweis", "first": "james"},
        "FABRIKANT, DAVID": {"last": "fabrikant", "first": "dave"}, 
        "EVANS, RICHARD": {"last": "evans", "first": "rick"}        
    }
    
    # === MANUAL PARTY OVERRIDES ===
    PARTY_OVERRIDES = {
        "GILLESPIE, NEIL": "NPA",
        "SIMMONS, DEVA": "NPA",
        "COOKE, ALEXANDER": "NPA",
        "FABRIKANT, DAVID": "WRI",
        "DARO, ANDY": "IND",
        "GONZALEZ, PATRICIA": "WRI",
        "HAMILTON, MICHAELANGELO": "WRI",
        "MEIDINGER HOSEY, DEBORAH": "WRI",
        "ROJAS, EDDY": "NPA"
    }

    for s_cand in state_roster:
        matched_fec_node = None
        display_name = s_cand['clean_display_name']
        
        if display_name in PARTY_OVERRIDES:
            s_cand['party_full'] = PARTY_OVERRIDES[display_name]
        
        if display_name in MANUAL_OVERRIDES:
            s_last = MANUAL_OVERRIDES[display_name]["last"]
            s_first = MANUAL_OVERRIDES[display_name]["first"]
        else:
            s_last = clean_name_string(s_cand['last_name'])
            s_first = clean_name_string(s_cand['first_name'])
        
        for f_cand in fec_pool:
            fec_name_raw = f_cand.get('name', '').lower()
            if ',' not in fec_name_raw: continue
            
            f_parts = fec_name_raw.split(',', 1)
            f_last = clean_name_string(f_parts[0])
            f_first = clean_name_string(f_parts[1])
            
            if s_last == f_last:
                if (s_first in f_first) or (f_first in s_first) or any(p in f_first for p in s_first.split() if len(p) > 2):
                    matched_fec_node = f_cand
                    break
                    
        if not matched_fec_node:
            print(f"   ⚠️ Name Crosswalk miss for: {s_cand['clean_display_name']} - Adding to tracker with $0")
            cand_id = "NO_FEC_ID"
        else:
            cand_id = matched_fec_node.get('candidate_id')
            print(f"✅ Paired: {s_cand['clean_display_name']} ➔ FEC ID: {cand_id}")
        
        candidate_obj = {
            "name": s_cand['clean_display_name'],
            "id": cand_id,
            "party_full": s_cand['party_full'],
            "office_full": s_cand['office_full'],
            "counties": s_cand['counties'],
            "receipts": 0,
            "pac_money": 0,
            "loans": 0,
            "disbursements": 0,
            "cash_on_hand": 0,
            "joint_funds": []
        }
        
        if cand_id != "NO_FEC_ID":
            try:
                url_comm = f"{BASE_URL}/candidate/{cand_id}/committees/"
                res_comm = fec_session.get(url_comm, params={"api_key": API_KEY, "cycle": CYCLE, "designation": "P"}, timeout=20)
                
                if res_comm.status_code == 200 and res_comm.json().get('results'):
                    p_id = res_comm.json()['results'][0].get('committee_id')
                    
                    res_tot = fec_session.get(f"{BASE_URL}/committee/{p_id}/totals/", params={"api_key": API_KEY, "cycle": CYCLE}, timeout=20)
                    if res_tot.status_code == 200 and res_tot.json().get('results'):
                        p_data = res_tot.json()['results'][0]
                        candidate_obj.update({
                            "receipts": p_data.get('receipts', 0),
                            "pac_money": p_data.get('contributions_from_other_political_committees', 0),
                            "loans": p_data.get('loans_received_from_candidate', 0) + p_data.get('other_loans_received', 0),
                            "disbursements": p_data.get('disbursements', 0),
                            "cash_on_hand": p_data.get('last_cash_on_hand_end_period', 0)
                        })
                    
                    res_jfc = fec_session.get(f"{BASE_URL}/committees/", params={"api_key": API_KEY, "cycle": CYCLE, "q": s_cand['clean_display_name'], "designation": "J"}, timeout=20)
                    if res_jfc.status_code == 200:
                        for jfc in res_jfc.json().get('results', []):
                            j_id = jfc.get('committee_id')
                            res_j_tot = fec_session.get(f"{BASE_URL}/committee/{j_id}/totals/", params={"api_key": API_KEY, "cycle": CYCLE}, timeout=20)
                            
                            if res_j_tot.status_code == 200 and res_j_tot.json().get('results'):
                                j_data = res_j_tot.json()['results'][0]
                                candidate_obj["joint_funds"].append({
                                    "name": jfc.get('name'), 
                                    "id": j_id,
                                    "receipts": j_data.get('receipts', 0), 
                                    "disbursements": j_data.get('disbursements', 0), 
                                    "cash_on_hand": j_data.get('last_cash_on_hand_end_period', 0)
                                })
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Network timeout fetching committee financial data for {s_cand['clean_display_name']} - Skipping financials")
        
        master_output.append(candidate_obj)
        time.sleep(0.1)

    os.makedirs('data', exist_ok=True)
    with open('data/election_data.json', 'w') as f:
        json.dump(master_output, f, indent=2)
    print(f"🎉 Build Complete. Integrated architecture mapped to data/election_data.json")

if __name__ == "__main__":
    main()