import requests
import pandas as pd

base_url = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/properties_reported_2024/FeatureServer/0/query"

# We use the params dictionary to make the URL much cleaner and easier to read
params = {
    "where": "primary_prop_type_epa_calc IN ('Multifamily Housing', 'Office', 'Retail Store', 'Wholesale Distribution Center', 'Self-Storage Facility') AND site_eui_kbtuft2 IS NOT NULL",
    "outFields": "*",
    "outSR": "4326",
    "f": "geojson",
    "resultRecordCount": 1000, # Ask for 1000 at a time
    "resultOffset": 0          # Start at row 0
}

all_buildings = []

print("Connecting to Philadelphia ArcGIS API...")

# The Pagination Loop
while True:
    response = requests.get(base_url, params=params)
    data = response.json()
    
    # Extract the features (rows) from this specific chunk
    features = data.get('features', [])
    
    # If the chunk is empty, we've reached the end of the database! Break the loop.
    if not features:
        break
        
    all_buildings.extend(features)
    print(f"Fetched {len(all_buildings)} records so far...")
    
    # ArcGIS tells us if there is more data waiting via the 'exceededTransferLimit' flag
    # If it's True, we increase our offset to get the next page. If not, we are done.
    if data.get('exceededTransferLimit') or len(features) == params['resultRecordCount']:
        params['resultOffset'] += params['resultRecordCount']
    else:
        break

print(f"\nFinished! Total leasable properties downloaded: {len(all_buildings)}")

# Flatten the GeoJSON into a Pandas DataFrame
df_data = [feature['properties'] for feature in all_buildings]
df = pd.DataFrame(df_data)

# Extract coordinates
df['longitude'] = [feature['geometry']['coordinates'][0] for feature in all_buildings]
df['latitude'] = [feature['geometry']['coordinates'][1] for feature in all_buildings]

# Save the full, un-capped dataset
df.to_csv("ai/philly_buildings.csv", index=False)
print("Data successfully saved to ai/philly_buildings.csv")