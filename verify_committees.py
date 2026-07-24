import os
import pandas as pd

def audit_potential_committees():
    cand_file = "fl_2026_state_tracker_latest.csv"
    com_file = "dos_master_committees.csv"
    audit_output = "POTENTIAL_COMMITTEES_TO_REVIEW.csv"

    if not os.path.exists(cand_file):
        print(f"[!] Missing {cand_file}. Run fetch_state_candidates.py first.")
        return

    if not os.path.exists(com_file):
        print(f"[!] Missing {com_file}. Please save your cleaned state committee export as a CSV in this directory.")
        return

    print("Loading clean candidate and committee datasets into Pandas...")
    cand_df = pd.read_csv(cand_file, dtype=str)
    com_df = pd.read_csv(com_file, dtype=str)

    # Standardize and strip whitespace from all column headers safely
    com_df.columns = com_df.columns.str.strip()
    
    # Check for the required columns to ensure your CSV export didn't rename anything
    required_cols = ['AcctNum', 'Name', 'ChrNameLast', 'ChrNameFirst']
    missing_cols = [col for col in required_cols if col not in com_df.columns]
    if missing_cols:
        print(f"[!] Critical Error: Your CSV is missing these expected headers: {missing_cols}")
        print(f"Available headers in your file are: {list(com_df.columns)}")
        return

    review_list = []
    print("Auditing candidate roster against verified chairperson data layout...")

    # Normalize search columns to lowercase and strip whitespace to prevent missed matches
    com_df['ChrNameLast_clean'] = com_df['ChrNameLast'].str.lower().str.strip().fillna('')
    com_df['ChrNameFirst_clean'] = com_df['ChrNameFirst'].str.lower().str.strip().fillna('')
    com_df['Name_clean'] = com_df['Name'].str.lower().fillna('')

    for _, cand in cand_df.iterrows():
        cand_id = cand['candidate_id']
        cand_name = str(cand['name']).lower().strip()
        
        name_parts = cand_name.split()
        if len(name_parts) < 2:
            continue
            
        first_name = name_parts[0]
        last_name = name_parts[-1]

        # Use Pandas vectorized lookups to instantly isolate matching last names
        matched_rows = com_df[com_df['ChrNameLast_clean'] == last_name]

        for _, committee in matched_rows.iterrows():
            com_first = committee['ChrNameFirst_clean']
            com_name = committee['Name_clean']
            
            # Guardrail match verification
            if first_name in com_first or last_name in com_name:
                review_list.append({
                    'CANDIDATE_ID': cand_id,
                    'CANDIDATE_NAME': cand['name'],
                    'VERIFIED_PC_ID': str(committee['AcctNum']).strip(),
                    'COMMITTEE_NAME': str(committee['Name']).strip(),
                    'COMMITTEE_CHAIR': f"{str(committee['ChrNameFirst']).strip()} {str(committee['ChrNameLast']).strip()}".title(),
                    'COMMITTEE_TYPE': str(committee.get('TypeDesc', 'Political Committee')).strip()
                })

    if review_list:
        audit_df = pd.DataFrame(review_list)
        # Prevent row duplication
        audit_df = audit_df.drop_duplicates(subset=['CANDIDATE_ID', 'VERIFIED_PC_ID'])
        audit_df.to_csv(audit_output, index=False)
        print(f"\n--- SUCCESS ---")
        print(f"Generated a clean audit sheet with {len(audit_df)} rock-solid potential committee matches.")
        print(f"Review the results safely here: '{audit_output}'")
    else:
        print("\nNo certain committee pairings discovered via chairperson alignments.")

if __name__ == "__main__":
    audit_potential_committees()