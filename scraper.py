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
            print(f" ➔ Found {len(qualified_candidates)} officially qualified South Florida federal candidates.")
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
    params = {"api_key": API_KEY, "state": "FL", "cycle": CYCLE, "per_page": 100}
    
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

def fetch_committee_financials(comm_id):
    """Helper to safely fetch 2026 totals for a specific committee ID."""
    endpoint = f"{BASE_URL}/committee/{comm_id}/totals/"
    try:
        res = fec_session.get(endpoint, params={"api_key": API_KEY, "cycle": CYCLE}, timeout=20)
        if res.status_code == 200 and res.json().get('results'):
            for record in res.json()['results']:
                if str(record.get('cycle')) == str(CYCLE):
                    return record
            return res.json()['results'][0]
    except Exception as e:
        print(f"   ⚠️ Error fetching totals for committee {comm_id}: {e}")
    return {}

def main():
    print(f"[{datetime.now()}] Initializing clean committee data matrix...")
    state_roster = get_state_roster()
    
    if not state_roster:
        print("🚨 Run halted: State authoritative master block is empty.")
        return
        
    fec_pool = fetch_fec_bulk_pool()
    master_output = []

    # Audited Manual Overrides to map legacy or shortened incumbent crosswalks safely
    MANUAL_OVERRIDES = {
        "FRANKEL, LOIS": {"last": "frankel", "first": "lois"},
        "NIXON, ANGIE": {"last": "nixon", "first": "angela"},
        "KAUFMAN, JOSEPH": {"last": "kaufman", "first": "joe"},
        "OBERWEIS, JIM": {"last": "oberweis", "first": "james"},
        "FABRIKANT, DAVID": {"last": "fabrikant", "first": "dave"}, 
        "EVANS, RICHARD": {"last": "evans", "first": "rick"}        
    }
    
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

    # USER REVISED ACTUAL VERIFIED FINANCIAL MATRIX
    HARDCODED_FINANCIALS = {
        "FRANKEL, LOIS": {
            "receipts": 2215066.45,
            "disbursements": 927145.05,
            "cash_on_hand": 1287921.40,  # Dynamically tracked down from new entries
            "loans": 0.0
        }
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
        
        if display_name in HARDCODED_FINANCIALS:
            print(f"   ⚠️ Injecting revised actual user financial overrides for: {display_name}")
            candidate_obj.update(HARDCODED_FINANCIALS[display_name])
            
        elif cand_id != "NO_FEC_ID":
            try:
                url_comm = f"{BASE_URL}/candidate/{cand_id}/committees/"
                res_comm = fec_session.get(url_comm, params={"api_key": API_KEY}, timeout=20)
                
                if res_comm.status_code == 200:
                    committees = res_comm.json().get('results', [])
                    
                    for comm in committees:
                        c_id = comm.get('committee_id')
                        c_name = comm.get('name')
                        designation = comm.get('designation')
                        designation_full = comm.get('designation_full', '').lower()
                        
                        p_data = fetch_committee_financials(c_id)
                        
                        by_candidate = float(p_data.get('loans_made_by_candidate', 0) or 0)
                        other_loans = float(p_data.get('other_loans_received', 0) or 0)
                        generic_loans = float(p_data.get('loans_received', 0) or 0)
                        calculated_total_loans = by_candidate + other_loans + generic_loans
                        
                        fec_receipts = p_data.get('receipts') if p_data.get('receipts') is not None else p_data.get('total_receipts', 0)
                        fec_disbursements = p_data.get('disbursements') if p_data.get('disbursements') is not None else p_data.get('total_disbursements', 0)
                        fec_coh = p_data.get('cash_on_hand_end_period') if p_data.get('cash_on_hand_end_period') is not None else p_data.get('last_cash_on_hand_end_period', 0)
                        
                        has_active_totals = (
                            float(fec_receipts or 0) > 0 or 
                            float(fec_disbursements or 0) > 0 or 
                            float(fec_coh or 0) > 0 or
                            calculated_total_loans > 0
                        )
                        
                        if designation == "P" or "principal" in designation_full:
                            candidate_obj.update({
                                "receipts": fec_receipts,
                                "loans": calculated_total_loans,
                                "disbursements": fec_disbursements,
                                "cash_on_hand": fec_coh
                            })
                        else:
                            if has_active_totals:
                                candidate_obj["joint_funds"].append({
                                    "name": c_name, 
                                    "id": c_id,
                                    "receipts": fec_receipts, 
                                    "disbursements": fec_disbursements, 
                                    "cash_on_hand": fec_coh,
                                    "loans": calculated_total_loans
                                })
                            
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Network timeout fetching committee financial data for {s_cand['clean_display_name']} - Skipping financials")
        
        master_output.append(candidate_obj)
        time.sleep(0.2)

    os.makedirs('data', exist_ok=True)
    with open('data/election_data.json', 'w') as f:
        json.dump(master_output, f, indent=2)
    print(f"🎉 Build Complete. Mapped actual overrides cleanly to data/election_data.json")

if __name__ == "__main__":
    main()
    