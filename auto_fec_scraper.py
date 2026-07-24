import requests

# ==========================================
# FEC API CONFIGURATION
# ==========================================
API_KEY = "l0hX7OVEFfgsSxPWOggS3AQ8xy6D3bcixJ8rifcJ"  # Drop your real key here
CYCLE = "2026"

# You can add as many Florida candidate IDs to this list as you want.
# The script will do all the heavy lifting automatically.
FLORIDA_CANDIDATES = [
    "S6FL00640", # Ashley Moody
]

def fetch_fec(endpoint, **kwargs):
    """Helper function to cleanly hit the FEC API with parameters."""
    url = f"https://api.open.fec.gov/v1{endpoint}"
    params = {"api_key": API_KEY, "cycle": CYCLE}
    params.update(kwargs)
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        print(f"❌ API Error on {endpoint}: {e}")
        return []

def format_money(amount):
    """Helper to format raw numbers into currency strings."""
    return f"${int(amount):,}" if amount else "$0"

def main():
    print("🚀 Initializing Automated Florida FEC Network Scraper...\n")
    
    for cand_id in FLORIDA_CANDIDATES:
        print("=" * 70)
        
        # 1. Get the Candidate's Official Name
        candidate_data = fetch_fec(f"/candidate/{cand_id}/")
        if not candidate_data:
            continue
            
        raw_name = candidate_data[0].get('name', '')
        print(f"👤 Analyzing Candidate: {raw_name} ({cand_id})")
        
        # Format "MOODY, ASHLEY" to "ASHLEY MOODY" for the search query
        parts = [p.strip() for p in raw_name.split(',')]
        if len(parts) == 2:
            search_name = f"{parts[1]} {parts[0]}"
        else:
            search_name = raw_name
            
        # 2. Get the Principal Campaign Committee
        principal_committees = fetch_fec(f"/candidate/{cand_id}/committees/", designation="P")
        
        # 3. Automatically Discover Joint Fundraising Committees
        # Because of FEC naming laws, we can just search for designation "J" with their name!
        jfcs = fetch_fec("/committees/", q=search_name, designation="J")
        
        # Combine the discovered committees
        all_committees = principal_committees + jfcs
        
        if not all_committees:
            print("No committees found.")
            continue
            
        # 4. Fetch the financial totals for every discovered committee
        for committee in all_committees:
            c_id = committee.get('committee_id')
            c_name = committee.get('name')
            c_type = "🎯 Principal Campaign" if committee.get('designation') == 'P' else "🔗 Joint Fundraiser"
            
            totals = fetch_fec(f"/committee/{c_id}/totals/")
            if not totals:
                continue
                
            data = totals[0]
            raised = data.get('receipts', 0)
            spent = data.get('disbursements', 0)
            cash = data.get('last_cash_on_hand_end_period', 0)
            
            print(f"\n{c_type}: {c_name} ({c_id})")
            print(f"   Raised: {format_money(raised)} | Spent: {format_money(spent)} | Cash: {format_money(cash)}")

if __name__ == "__main__":
    main()