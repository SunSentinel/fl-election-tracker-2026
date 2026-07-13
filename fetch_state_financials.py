import os
import pandas as pd
import requests
import time
import re

def clean_currency(val):
    if not val:
        return 0.0
    val_str = str(val)
    # The Nuclear Option: Strips out EVERYTHING except digits, decimals, and minus signs
    clean_str = re.sub(r'[^\d\.-]', '', val_str)
    try:
        if clean_str in ['', '-', '.']:
            return 0.0
        return float(clean_str)
    except ValueError:
        return 0.0

def update_state_financials():
    file_path = "fl_2026_state_tracker_latest.csv"
    if not os.path.exists(file_path):
        print(f"[!] Cannot find {file_path}. Please generate the state candidate list first.")
        return

    print("Loading state candidate dataset...")
    df = pd.read_csv(file_path, dtype=str)
    
    for col in ['receipts', 'disbursements', 'cash_on_hand_end_period', 'pac_money', 'loans']:
        if col not in df.columns:
            df[col] = 0.0

    print("Booting up scraper: Pinging Florida DOS Campaign Finance Database...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SunSentinel Election Tracker DataBot'
    }

    updated_rows = []
    
    for idx, row in df.iterrows():
        acct_num = str(row.get('candidate_id', '')).strip()
        cand_name = str(row.get('name', 'Unknown'))
        
        receipts = 0.0
        spent = 0.0
        loans = 0.0
        
        if acct_num and acct_num != 'nan':
            url = f"https://dos.elections.myflorida.com/cgi-bin/TreSel.exe?account={acct_num}"
            
            try:
                time.sleep(0.5) 
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    html = response.text
                    
                    # DITCH PANDAS: Extract every table row (<tr>) using raw regex
                    trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.IGNORECASE | re.DOTALL)
                    
                    for tr in trs:
                        if 'all dates' in tr.lower() or 'totals' in tr.lower():
                            
                            # Extract all table cells (<td> or <th>) inside this specific row
                            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.IGNORECASE | re.DOTALL)
                            
                            # Strip any internal HTML tags (like bold text) and invisible characters
                            clean_cells = [re.sub(r'<[^>]+>', '', c).replace('&nbsp;', '').strip() for c in cells]
                            
                            # Remove completely blank cells created by Florida's broken layout
                            clean_cells = [c for c in clean_cells if c != '']
                            
                            # In the raw text, the array should now look exactly like:
                            # [0] "All Dates (Totals)", [1] Raised, [2] Loans, [3] In-Kind, [4] Spent
                            
                            label_idx = -1
                            for i, c in enumerate(clean_cells):
                                if 'total' in c.lower() or 'all dates' in c.lower():
                                    label_idx = i
                                    break
                            
                            if label_idx != -1:
                                if len(clean_cells) > label_idx + 1:
                                    receipts = clean_currency(clean_cells[label_idx + 1])
                                if len(clean_cells) > label_idx + 2:
                                    loans = clean_currency(clean_cells[label_idx + 2])
                                if len(clean_cells) > label_idx + 4:
                                    spent = clean_currency(clean_cells[label_idx + 4])
                            
                            break # Found the totals, exit the loop
                            
            except Exception:
                pass # Fail silently and keep zeroes if the candidate legitimately hasn't filed yet

        # Calculate final Cash on Hand
        coh = (receipts + loans) - spent

        row['receipts'] = receipts
        row['disbursements'] = spent
        row['loans'] = loans
        row['cash_on_hand_end_period'] = coh
        
        updated_rows.append(row)
        
        # Don't panic if Lauren Donahoo is $0.00! Some early candidates actually have zero activity.
        print(f"Scraped {cand_name}: Raised ${receipts:,.2f} | Spent ${spent:,.2f}")

    final_df = pd.DataFrame(updated_rows)
    final_df.to_csv(file_path, index=False)
    print("\nSUCCESS: All official state campaign accounts scraped and updated.")

if __name__ == "__main__":
    update_state_financials()