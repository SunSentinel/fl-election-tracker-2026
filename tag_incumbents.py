import pandas as pd
import os

def rapid_fire_incumbents():
    file_path = 'fl_2026_state_tracker_latest.csv'
    if not os.path.exists(file_path):
        print(f"[!] Cannot find {file_path}. Run fetch_state_candidates.py first.")
        return

    df = pd.read_csv(file_path, dtype=str)
    
    # Sort by office so it's easy for you to think through the map geographically
    df = df.sort_values(by='office_full')
    
    incumbents = []
    
    print("\n=== RAPID-FIRE INCUMBENT TAGGER ===")
    print("Type 'y' and press Enter if the candidate is the incumbent for the EXACT seat they are seeking.")
    print("Otherwise, just press Enter to skip them.")
    print("Type 'q' and press Enter at any time to save your progress and quit.\n")
    
    for idx, row in df.iterrows():
        cand_name = str(row.get('name', 'Unknown')).strip()
        office = str(row.get('office_full', 'Unknown')).strip()
        party = str(row.get('party_full', '')).strip()
        
        ans = input(f"{office} | {cand_name} ({party}) -> Incumbent? (y/n): ").strip().lower()
        
        if ans == 'q':
            break
        elif ans == 'y':
            incumbents.append({'candidate_id': row['candidate_id']})
            
    if incumbents:
        inc_df = pd.DataFrame(incumbents)
        inc_df.to_csv('state_incumbents.csv', index=False)
        print(f"\nSUCCESS: Saved {len(incumbents)} incumbents perfectly into state_incumbents.csv!")
    else:
        print("\nNo incumbents tagged. File not created.")

if __name__ == "__main__":
    rapid_fire_incumbents()