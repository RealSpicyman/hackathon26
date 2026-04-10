import requests
import pandas as pd

# The engineered URL
url = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/properties_reported_2024/FeatureServer/0/query?outFields=*&where=primary_prop_type_epa_calc+IN+('Multifamily+Housing'%2C+'Office'%2C+'Retail+Store'%2C+'Wholesale+Distribution+Center'%2C+'Self-Storage+Facility')+AND+site_eui_kbtuft2+IS+NOT+NULL&outSR=4326&f=geojson&resultRecordCount=10000"

# Fetch the data
response = requests.get(url)
data = response.json()

# Because we used geojson, the actual building data is stored inside the 'properties' key of each feature
building_data = [feature['properties'] for feature in data['features']]

# Create the DataFrame
df = pd.DataFrame(building_data)

# Optional: Grab the Latitude and Longitude if you want to map it or use it as an ML feature
df['longitude'] = [feature['geometry']['coordinates'][0] for feature in data['features']]
df['latitude'] = [feature['geometry']['coordinates'][1] for feature in data['features']]

print(f"Successfully loaded {len(df)} leasable properties ready for AI training.")

# Save the data locally so the AI can train on it without re-downloading
df.to_csv("ai/philly_buildings.csv", index=False)
print("Data saved to ai/philly_buildings.csv")