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

        return {
            "status": "found_in_database",
            "name": prop_name,
            "address": str(best_match['street_address']).title(),
            "type": str(best_match['primary_prop_type_epa_calc']),
            "sqft": int(best_match['total_floor_area_bld_pk_ft2']),
            "grade": str(best_match['Grade']),
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
def predict_property_grade(sqft: int, year_built: int, property_type: str, lat: float, lon: float):
    """
    This endpoint uses the trained Machine Learning model to predict a grade.
    Example: /api/predict?sqft=65000&year_built=2015&property_type=Office&lat=39.95&lon=-75.16
    """
    try:
        # 1. Package the user's input into a Pandas DataFrame.
        # Ensure column names match EXACTLY what the model saw during training.
        input_data = pd.DataFrame([{
            'year_built': year_built,
            'total_floor_area_bld_pk_ft2': sqft,
            'primary_prop_type_epa_calc': property_type,
            'latitude': lat,
            'longitude': lon
        }])

        # 2. Feed the data to the AI model
        prediction_array = model.predict(input_data)
        predicted_grade = prediction_array[0]

        # 3. Return the AI's answer
        return {
            "status": "ai_predicted",
            "name": "AI Estimate",
            "type": property_type,
            "sqft": sqft,
            "year_built": year_built,
            "grade": str(predicted_grade),
            "confidence": f"AI Estimated (Location: {lat:.4f}, {lon:.4f})"
        }
        
    except Exception as e:
        # This will now catch if the model expects different column names
        return {"error": f"AI Prediction Failed: {str(e)}"}