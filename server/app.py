from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse 
from fastapi.staticfiles import StaticFiles
import pandas as pd
import joblib
from pathlib import Path
import sys

app = FastAPI()

# This allows your HTML file to securely talk to this Python server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Starting server... Loading brain...")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "philly_buildings_graded.csv"
MODEL_PATH = PROJECT_ROOT / "property_rating_model.pkl"
ASSETS_PATH = PROJECT_ROOT / "assets"
CSS_PATH = PROJECT_ROOT / "css"
INDEX_PATH = PROJECT_ROOT / "index.html"

# Check if files actually exist before trying to read them
if not DATASET_PATH.exists() or not MODEL_PATH.exists():
    print(f"\nCRITICAL ERROR: Could not find the required files!")
    print(f"Looking for data in: {DATASET_PATH}")
    print(f"Looking for model in: {MODEL_PATH}")
    print("Please make sure the files are in the correct folder.")
    sys.exit(1) # Kill the server immediately

df = pd.read_csv(DATASET_PATH, on_bad_lines='skip')

# Strip any invisible spaces from all column headers
df.columns = df.columns.str.strip()

df['street_address'] = df['street_address'].astype(str).str.lower().str.strip()
address_index = df['street_address'].dropna().drop_duplicates().tolist()
model = joblib.load(MODEL_PATH)
print("Brain successfully loaded!")

app.mount("/assets", StaticFiles(directory=str(ASSETS_PATH)), name="assets")
app.mount("/css", StaticFiles(directory=str(CSS_PATH)), name="css")


# --- UPDATED: Serve the HTML file when someone visits the root URL ---
@app.get("/")
def serve_home():
    return FileResponse(str(INDEX_PATH))


@app.get("/api/search")
def search_property(address: str):
    """
    Search the database for an exact address match.
    """
    search_query = address.lower().strip()
    
    # Added regex=False to prevent crashes if the user types special characters like (.) or (#)
    match = df[df['street_address'].str.contains(search_query, na=False, regex=False)]
    
    if not match.empty:
        best_match = match.iloc[0]
        prop_name = str(best_match['property_name'])
        if prop_name == 'nan':
            prop_name = "Property Name Not Provided"

        # Safely handle the EPA Energy Star Score (some buildings don't have one)
        energy_star = best_match['energy_star_score']
        if pd.isna(energy_star) or str(energy_star).strip().lower() == 'nan':
            energy_star = "N/A"
        else:
            energy_star = int(energy_star)

        return {
            "status": "found_in_database",
            "name": prop_name,
            "address": str(best_match['street_address']).title(),
            "type": str(best_match['primary_prop_type_epa_calc']),
            "sqft": int(best_match['total_floor_area_bld_pk_ft2']),
            "grade": str(best_match['Grade']),
            # --- NEW TIER 1 / UNDERLYING METRICS ---
            "energy_star_score": energy_star,
            "composite_score": round(float(best_match['composite_score']) * 100, 1),
            "eui_percentile": round(float(best_match['eui_score']) * 100, 1),
            "ghg_percentile": round(float(best_match['ghg_score']) * 100, 1),
            "water_percentile": round(float(best_match['water_score']) * 100, 1),
            "confidence": "100% (Calculated from City Benchmarks)"
        }
    
    # If the code makes it down here, it MUST return this dictionary!
    return {"error": "Property not found in the 2024 Benchmarking Dataset."}
@app.get("/api/suggest")
def suggest_addresses(query: str):
    """
    Return matching street address suggestions once user input is specific enough.
    """
    search_query = query.lower().strip()
    if len(search_query) < 5:
        return {"suggestions": []}

    suggestions = [
        address.title()
        for address in address_index
        if search_query in address
    ]

    return {"suggestions": suggestions}

 
# AI MODEL PREDICTION
@app.get("/api/predict")
def predict_property_grade(lat: float, lon: float):
    try:
        # 1. Provide default values for the features the model expects
        # These should ideally be the median/mode of your training data
        input_data = pd.DataFrame([{
            'latitude': lat,
            'longitude': lon,
            'total_floor_area_bld_pk_ft2': 50000,  # Average SqFt placeholder
            'year_built': 1960,                   # Average Year placeholder
            'primary_prop_type_epa_calc': 'Office' # Most common type placeholder
        }])

        # 2. Reorder columns if necessary (some models require the exact training order)
        # Ensure these are in the EXACT order the model was trained on
        column_order = ['year_built', 'total_floor_area_bld_pk_ft2', 
                        'primary_prop_type_epa_calc', 'latitude', 'longitude']
        input_data = input_data[column_order]

        # 3. Feed the data to the AI model
        prediction_array = model.predict(input_data)
        predicted_grade = prediction_array[0]

        return {
            "status": "ai_predicted",
            "name": "Location-Based Estimate",
            "grade": str(predicted_grade),
            "coordinates": {"lat": lat, "lon": lon},
            "confidence": "AI Estimated (Location-only mode)"
        }
        
    except Exception as e:
        return {"error": f"AI Prediction Failed: {str(e)}"}