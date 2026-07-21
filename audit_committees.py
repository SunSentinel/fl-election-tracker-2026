import os
import requests

FEC_API_KEY = os.getenv("FEC_API_KEY")
# Target Debbie Wasserman Schultz's unique candidate ID
CANDIDATE_ID = "H4FL20023" 

url = f"https://api.open.fec.gov/v1/candidate/{CANDIDATE_ID}/committees/?api_key={FEC_API_KEY}"
response = requests.get(url).json()

print(f"--- ACTIVE FEC COMMITTEES FOR {CANDIDATE_ID} ---")
for committee in response.get('results', []):
    print(f"Name: {committee['name']}")
    print(f"ID: {committee['committee_id']}")
    print(f"Type: {committee['committee_type_full']}")
    print(f"Designation: {committee['designation_full']}")
    print("-" * 40)