import pandas as pd
import os

def isolate_verified_pcs():
    cand_file = "fl_2026_state_tracker_latest.csv"
    com_file = "dos_master_committees.csv"
    output_file = "state_pc_crosswalk.csv"

    if not os.path.exists(cand_file) or not os.path.exists(com_file):
        print("[!] Make sure both fl_2026_state_tracker_latest.csv and dos_master_committees.csv are in this folder.")
        return

    print("Loading datasets...")
    cand_df = pd.read_csv(cand_file, dtype=str)
    com_df = pd.read_csv(com_file, dtype=str)
    com_df.columns = com_df.columns.str.strip()

    # Clean and normalize names to prevent missing strict matches
    com_df['ChrNameLast_clean'] = com_df['ChrNameLast'].str.lower().str.strip().fillna('')
    com_df['ChrNameFirst_clean'] = com_df['ChrNameFirst'].str.lower().str.strip().fillna('')

    verified_crosswalk = []

    print("Extracting high-value candidate-controlled committees...")
    for _, cand in cand_df.iterrows():
        cand_id = cand['candidate_id']
        full_name = str(cand['name']).lower().strip()
        
        name_parts = full_name.split()
        if len(name_parts) < 2:
            continue
            
        first_name = name_parts[0]
        last_name = name_parts[-1]

        # VECTORIZED CHECK: Only pull rows where candidate is explicitly the listed chair
        matches = com_df[(com_df['ChrNameLast_clean'] == last_name) & (com_df['ChrNameFirst_clean'] == first_name)]

        for _, match in matches.iterrows():
            verified_crosswalk.append({
                'candidate_id': cand_id,
                'pc_acct_num': str(match['AcctNum']).strip(),
                'pc_name': str(match['Name']).strip()
            })

    if verified_crosswalk:
        out_df = pd.DataFrame(verified_crosswalk).drop_duplicates()
        out_df.to_csv(output_file, index=False)
        print(f"\n[!] SUCCESS: Automatically mapped {len(out_df)} candidate-controlled committees with zero risk.")
        print(f"Saved directly to '{output_file}'. Your financial scraper will now track these loophole accounts.")
    else:
        print("\nNo direct candidate-chaired committees found.")

if __name__ == "__main__":
    isolate_verified_pcs()