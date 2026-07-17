import pandas as pd

# Florida County FIPS code dictionary (12 is the state code, the last 3 digits are the county)
FL_FIPS_TO_COUNTY = {
    '001': 'Alachua', '003': 'Baker', '005': 'Bay', '007': 'Bradford', '009': 'Brevard',
    '011': 'Broward', '013': 'Calhoun', '015': 'Charlotte', '017': 'Citrus', '019': 'Clay',
    '021': 'Collier', '023': 'Columbia', '025': 'Dade', '027': 'DeSoto', '029': 'Dixie',
    '031': 'Duval', '033': 'Escambia', '035': 'Flagler', '037': 'Franklin', '039': 'Gadsden',
    '041': 'Gilchrist', '043': 'Glades', '045': 'Gulf', '047': 'Hamilton', '049': 'Hardee',
    '051': 'Hendry', '053': 'Hernando', '055': 'Highlands', '057': 'Hillsborough', '059': 'Holmes',
    '061': 'Indian River', '063': 'Jackson', '065': 'Jefferson', '067': 'Lafayette', '069': 'Lake',
    '071': 'Lee', '073': 'Leon', '075': 'Levy', '077': 'Liberty', '079': 'Madison',
    '081': 'Manatee', '083': 'Marion', '085': 'Martin', '086': 'Miami-Dade', '087': 'Monroe',
    '089': 'Nassau', '091': 'Okaloosa', '093': 'Okeechobee', '095': 'Orange', '097': 'Osceola',
    '099': 'Palm Beach', '101': 'Pasco', '103': 'Pinellas', '105': 'Polk', '107': 'Putnam',
    '109': 'St. Johns', '111': 'St. Lucie', '113': 'Santa Rosa', '115': 'Sarasota', '117': 'Seminole',
    '119': 'Sumter', '121': 'Suwannee', '123': 'Taylor', '125': 'Union', '127': 'Volusia',
    '129': 'Wakulla', '131': 'Walton', '133': 'Washington'
}

def create_district_crosswalk():
    print("Reading the raw Florida EOGPCRP2026 Block Equivalency File...")
    
    try:
        # Most BEF files don't have headers and are comma separated: BLOCKID, DISTRICT
        df = pd.read_csv('EOGPCRP2026.txt', sep=',', header=None, dtype=str)
        
        # If the file has a header, it will have text in the first row. Let's check and adjust.
        if not df.iloc[0, 0].isdigit():
            df = pd.read_csv('EOGPCRP2026.txt', sep=',', dtype=str)
            df.columns = ['BLOCKID', 'DISTRICT']
        else:
            df.columns = ['BLOCKID', 'DISTRICT']

        print(f" -> Successfully loaded {len(df):,} census blocks.")

        # Extract the 3-digit county FIPS code (characters at index 2, 3, and 4)
        # E.g., '120110001001000' -> '011'
        df['FIPS'] = df['BLOCKID'].str[2:5]
        
        # Map the FIPS code to our county name dictionary
        df['County'] = df['FIPS'].map(FL_FIPS_TO_COUNTY)

        # Drop any unmatched rows or statewide filler
        df = df.dropna(subset=['County', 'DISTRICT'])

        # Group by District and get a unique list of Counties for each
        print("Mapping county overlaps...")
        crosswalk = df.groupby('DISTRICT')['County'].unique().apply(lambda x: ', '.join(sorted(x))).reset_index()
        
        # Clean up the column names for export
        crosswalk.columns = ['district_num', 'county_list']

        # Save to CSV
        export_name = 'district_counties.csv'
        crosswalk.to_csv(export_name, index=False)
        print(f"\nSUCCESS! Authoritative crosswalk saved to {export_name}")

    except Exception as e:
        print(f"[!] Error processing the text file: {e}")
        print("Make sure EOGPCRP2026.txt is in the same folder as this script.")

if __name__ == "__main__":
    create_district_crosswalk()