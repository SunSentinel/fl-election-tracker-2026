import os
import pandas as pd

def clean_name(name):
    return str(name).strip().title() if pd.notna(name) else ""

def generate_state_candidates():
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

    df['OfficeDesc'] = df['OfficeDesc'].fillna('')
    
    cabinet_pattern = 'Governor|Attorney General|Chief Financial Officer|Agriculture'
    is_cabinet = df['OfficeDesc'].str.contains(cabinet_pattern, case=False, na=False)
    
    is_leg = df['OfficeDesc'].str.contains('Senator|Representative', case=False, na=False) & ~df['OfficeDesc'].str.contains('United States', case=False, na=False)
    
    state_df = df[is_cabinet | is_leg].copy()
    
    if state_df.empty:
        print("No state candidates found in the master file.")
        return

    # LOAD THE COUNTY CROSSWALK
    crosswalk_file = 'state_district_counties.csv'
    FL_STATE_COUNTIES = {}
    if os.path.exists(crosswalk_file):
        cw_df = pd.read_csv(crosswalk_file, dtype=str)
        for _, cw_row in cw_df.iterrows():
            key = f"{str(cw_row.get('office', '')).strip()}_{str(cw_row.get('district_num', '')).strip()}"
            FL_STATE_COUNTIES[key] = str(cw_row.get('county_list', '')).strip()
    else:
        print(f"[!] Warning: {crosswalk_file} not found. County labels will not display.")

    output_data = []
    
    for _, row in state_df.iterrows():
        last = clean_name(row.get('NameLast'))
        first = clean_name(row.get('NameFirst'))
        middle = clean_name(row.get('NameMiddle'))
        suffix = clean_name(row.get('NameSuffix'))
        
        full_name = f"{first} {middle} {last}".replace("  ", " ").strip()
        if suffix:
            full_name = f"{full_name}, {suffix}"
        
        office_desc = str(row.get('OfficeDesc', '')).strip()
        juris1 = str(row.get('Juris1num', '')).strip()
        
        office_full = office_desc
        
        # Format Statewide Offices
        if any(cab in office_desc for cab in ['Governor', 'Attorney General', 'Chief Financial Officer', 'Agriculture']):
            office_full = f"{office_desc}|Statewide (All 67 Counties)"
            
        # Format Legislative Offices with County Crosswalk
        elif 'Senator' in office_desc or 'Representative' in office_desc:
            try:
                dist = int(float(juris1))
                cw_office = 'Senate' if 'Senator' in office_desc else 'House'
                lookup_key = f"{cw_office}_{dist}"
                
                counties = FL_STATE_COUNTIES.get(lookup_key, "")
                
                if counties:
                    office_full = f"{office_desc} (District {dist})|{counties}"
                else:
                    office_full = f"{office_desc} (District {dist})"
            except ValueError:
                office_full = f"{office_desc} {juris1}".strip()
                
        output_data.append({
            'candidate_id': row.get('AcctNum', ''), 
            'name': full_name,
            'office_full': office_full,
            'party_full': row.get('PartyName', 'Unknown'),
            'is_incumbent': 'N', 
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