import os
import pandas as pd

def clean_name(name):
    return str(name).strip().title() if pd.notna(name) else ""

def generate_state_candidates():
    # Pointing directly to your single master download file
    file_path = "dos_qualified.txt"
    if not os.path.exists(file_path):
        print(f"[!] Cannot find {file_path}. Please ensure it is in this folder.")
        return
        
    print(f"Loading state candidates directly from master file: {file_path}...")
    try:
        df = pd.read_csv(file_path, sep='\t', encoding='utf-8', dtype=str)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Filter for relevant state offices
    target_offices = ['Governor', 'Attorney General', 'Chief Financial Officer', 'Commissioner of Agriculture', 'State Senator', 'State Representative']
    pattern = '|'.join(target_offices)
    
    # Fill NaN values to avoid string matching errors
    df['OfficeDesc'] = df['OfficeDesc'].fillna('')
    state_df = df[df['OfficeDesc'].str.contains(pattern, case=False, na=False)].copy()
    
    if state_df.empty:
        print("No state candidates found in the master file. Double-check your filters on the DOS download.")
        return

    output_data = []
    
    for _, row in state_df.iterrows():
        # Clean and assemble the candidate's name
        last = clean_name(row.get('NameLast'))
        first = clean_name(row.get('NameFirst'))
        middle = clean_name(row.get('NameMiddle'))
        suffix = clean_name(row.get('NameSuffix'))
        
        full_name = f"{first} {middle} {last}".replace("  ", " ").strip()
        if suffix:
            full_name = f"{full_name}, {suffix}"
        
        # Format the office and district number
        office_desc = str(row.get('OfficeDesc', '')).strip()
        juris1 = str(row.get('Juris1num', '')).strip()
        
        office_full = office_desc
        if 'Senator' in office_desc or 'Representative' in office_desc:
            try:
                dist = int(float(juris1))
                office_full = f"{office_desc} (District {dist})"
            except ValueError:
                office_full = f"{office_desc} {juris1}".strip()
                
        output_data.append({
            'candidate_id': row.get('AcctNum', ''), # State internal ID
            'name': full_name,
            'office_full': office_full,
            'party_full': row.get('PartyName', 'Unknown'),
            'is_incumbent': 'N', # Placeholder to map incumbents later
            'receipts': 0.0,
            'disbursements': 0.0,
            'cash_on_hand_end_period': 0.0,
            'pac_money': 0.0,
            'loans': 0.0
        })

    final_df = pd.DataFrame(output_data)
    
    export_filename = "fl_2026_state_tracker_latest.csv"
    final_df.to_csv(export_filename, index=False)
    print(f"SUCCESS: Exported {len(final_df)} qualified state candidates to {export_filename}")

if __name__ == "__main__":
    generate_state_candidates()