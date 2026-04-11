import time
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# --- PART 1: FETCH BUILDINGS ---
base_url = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/properties_reported_2024/FeatureServer/0/query"
params = {
    "where": "primary_prop_type_epa_calc IN ('Multifamily Housing', 'Office', 'Retail Store', 'Wholesale Distribution Center', 'Self-Storage Facility') AND site_eui_kbtuft2 IS NOT NULL",
    "outFields": "*",
    "outSR": "4326",
    "f": "geojson",
    "resultRecordCount": 1000,
    "resultOffset": 0
}

all_buildings = []
print("Connecting to Philadelphia ArcGIS API...")

while True:
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status() 
        
        data = response.json()
        features = data.get('features', [])
        
        if not features: 
            break
            
        all_buildings.extend(features)
        print(f"Fetched {len(all_buildings)} buildings...")
        
        if data.get('exceededTransferLimit') or len(features) == params['resultRecordCount']:
            params['resultOffset'] += params['resultRecordCount']
            time.sleep(1) 
        else: 
            break
            
    except requests.exceptions.Timeout:
        print("The request timed out! The ArcGIS API is taking too long to respond.")
        break
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        break

# Convert to GeoDataFrame
df_data = [f['properties'] for f in all_buildings]
df = pd.DataFrame(df_data)
geometry = [Point(f['geometry']['coordinates']) for f in all_buildings]
gdf_buildings = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


# --- PART 2: FETCH CRIME DATA ---
print("\nDownloading crime incident data (past 30 days)...")

crime_weights = {
    '100': 1.0, # Homicide
    '200': 1.0, # Rape
    '300': 0.8,  # Robbery
    '400': 0.8,  # Aggravated Assault
    '900': 0.8,  # Arson
    '1500': 0.6, # Weapon Violations
    '500': 0.5,  # Burglary
    '1700': 0.5, # Other Sex Offenses
    '700': 0.4,  # Motor Vehicle Theft
    '600': 0.3,  # Theft
    '2000': 0.3, # Family Offenses
    '2100': 0.2, # DUI
    '2300': 0.1  # Public Drunkenness
}

ucr_list = "', '".join(crime_weights.keys())

# --- Correct column name and URL-safe date math ---
crime_sql = f"SELECT the_geom, ucr_general FROM incidents_part1_part2 WHERE ucr_general IN ('{ucr_list}') AND dispatch_date_time >= current_date - 30"
# -----------------------------------------------------------

carto_url = f"https://phl.carto.com/api/v2/sql?q={crime_sql}&format=geojson"

try:
    crime_response = requests.get(carto_url, timeout=30)
    crime_response.raise_for_status()
    gdf_crime = gpd.GeoDataFrame.from_features(crime_response.json(), crs="EPSG:4326")
    print(f"Found {len(gdf_crime)} relevant incidents from the past month.")
    
    # Map the weights onto the crime dataframe
    gdf_crime['crime_weight'] = gdf_crime['ucr_general'].map(crime_weights)

except requests.exceptions.RequestException as e:
    print(f"Failed to fetch crime data: {e}")
    gdf_crime = gpd.GeoDataFrame(columns=['the_geom', 'ucr_general', 'crime_weight'], geometry='the_geom', crs="EPSG:4326")


# --- PART 3: SPATIAL CALCULATION ---
print("Calculating 1-mile radius weighted crime scores (in memory-safe chunks)...")

if not gdf_crime.empty and not gdf_buildings.empty:
    gdf_buildings = gdf_buildings.to_crs(epsg=3857)
    gdf_crime = gdf_crime.to_crs(epsg=3857)

    gdf_buildings_buffered = gdf_buildings.copy()
    gdf_buildings_buffered['geometry'] = gdf_buildings_buffered.buffer(1609.34)

    all_counts = []
    all_scores = []

    chunk_size = 2500 
    total_buildings = len(gdf_buildings_buffered)

    for i in range(0, total_buildings, chunk_size):
        print(f"Processing buildings {i} to {min(i + chunk_size, total_buildings)} of {total_buildings}...")
        
        chunk = gdf_buildings_buffered.iloc[i:i + chunk_size]
        joined_chunk = gpd.sjoin(chunk, gdf_crime, predicate='intersects', how='left')
        
        counts = joined_chunk.groupby(level=0).size() - joined_chunk['index_right'].isna().groupby(level=0).sum()
        scores = joined_chunk.groupby(level=0)['crime_weight'].sum().fillna(0)
        
        all_counts.append(counts)
        all_scores.append(scores)

    gdf_buildings['crime_count_5mi'] = pd.concat(all_counts).astype(int)
    gdf_buildings['crime_score_5mi_weighted'] = pd.concat(all_scores)
else:
    print("Skipping spatial calculation due to missing data.")
    gdf_buildings['crime_count_5mi'] = 0
    gdf_buildings['crime_score_5mi_weighted'] = 0.0


# --- PART 4: CLEANUP & SAVE ---
final_df = pd.DataFrame(gdf_buildings.drop(columns='geometry'))

columns_to_drop = [
    'philadelphia_building_id', 
    'objectid', 
    'x', 
    'y', 
    'id', 
    'source_eui_kbtuft2', 
    'index_right'
]

final_df = final_df.drop(columns=columns_to_drop, errors='ignore')

final_df.to_csv("ai/philly_buildings.csv", index=False)
print(f"Success! Data saved to ai/philly_buildings.csv.")
