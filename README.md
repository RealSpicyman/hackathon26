# Address Me

A FastAPI + JavaScript web app for searching Philadelphia properties and showing energy-efficiency grades.

The app tries a city benchmark dataset first, then falls back to an AI estimate when no exact record is found.

## What This Project Does

- Search by street address with live suggestions
- Return verified benchmark data when available
- Use geocoding when an address is missing from the dataset
- Predict a grade (`A` to `F`) using a trained ML model when needed
- Handle multiple location matches in the UI

## Project Structure

```text
hackathon26/
├── index.html
├── philly_buildings_graded.csv
├── property_rating_model.pkl
├── requirements.txt
├── server/
│   └── app.py
├── ai/
│   ├── trainModel.py
│   ├── fetchData.py
│   └── philly_buildings.csv
├── assets/
│   ├── css/
│   └── js/
│       └── scripts.js
└── css/
    └── pretty.css
```

## Tech Stack

- Backend: FastAPI
- Frontend: HTML, Bootstrap, vanilla JavaScript
- ML/Data: scikit-learn, pandas, numpy, joblib

## Prerequisites

- Python 3.10+
- pip

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure these files exist in the project root:
- `philly_buildings_graded.csv`
- `property_rating_model.pkl`

## Run the App

From the project root:

```bash
python -m uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000`

Note: If `uvicorn` is not installed in your environment, run:

```bash
pip install uvicorn
```

## API Endpoints

### `GET /`
Serves the web UI (`index.html`).

### `GET /api/suggest?query=<text>`
Returns matching street address suggestions.

Example response:

```json
{
  "suggestions": ["123 Market St", "1234 Market St"]
}
```

### `GET /api/search?address=<address>`
Searches the graded dataset for address matches.

Possible response (`found_in_database`):

```json
{
  "status": "found_in_database",
  "name": "Building Name",
  "address": "123 Market St",
  "type": "Office",
  "sqft": 50000,
  "grade": "B",
  "confidence": "100% (Calculated from City Benchmarks)"
}
```

Possible response (not found):

```json
{
  "error": "Property not found in the 2024 Benchmarking Dataset."
}
```

### `GET /api/predict`
Predicts a grade using the trained model.

Required query params:
- `sqft` (int)
- `year_built` (int)
- `property_type` (string)
- `lat` (float)
- `lon` (float)

Example:

```text
/api/predict?sqft=65000&year_built=2015&property_type=Office&lat=39.95&lon=-75.16
```

## Train or Retrain the Model

Run:

```bash
python ai/trainModel.py
```

This script will:
- load `ai/philly_buildings.csv`
- clean and engineer features
- build grades (`A`-`F`) using weighted scoring
- train a Random Forest pipeline
- output:
  - `philly_buildings_graded.csv`
  - `property_rating_model.pkl`

## Grade Weighting Used in Training

Defined in `ai/trainModel.py`:

- EUI: `0.40`
- GHG: `0.25`
- Water: `0.15`
- Crime: `0.20`

## Notes for Deployment

- `server/app.py` currently allows CORS from any origin (`allow_origins=["*"]`). Restrict this for production.
- Static assets are served from `/assets`.
- The app exits early if the dataset/model files are missing.

## Troubleshooting

- Server exits on startup:
  - Confirm `philly_buildings_graded.csv` and `property_rating_model.pkl` are in project root.
- `ModuleNotFoundError`:
  - Re-run `pip install -r requirements.txt`.
- API works but UI fails to load assets:
  - Confirm `assets/` folder exists at root and server is started from project root.
