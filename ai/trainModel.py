import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# Adjust these weights as needed. Ensure they add up to 1.0!
SCORE_WEIGHTS = {
    'eui': 0.40,
    'ghg': 0.25,
    'water': 0.15,
    'crime': 0.20
}

print("Loading data...")
# Load the data
df = pd.read_csv('ai/philly_buildings.csv', on_bad_lines='skip')
df.columns = df.columns.str.strip()

# ---------------------------------------------------------
# 1. Clean the Data
# ---------------------------------------------------------
# Force all relevant columns to be numeric
df['total_floor_area_bld_pk_ft2'] = pd.to_numeric(df['total_floor_area_bld_pk_ft2'], errors='coerce')
df['site_eui_kbtuft2'] = pd.to_numeric(df['site_eui_kbtuft2'], errors='coerce')
df['total_ghg_emissions_mtco2e'] = pd.to_numeric(df['total_ghg_emissions_mtco2e'], errors='coerce')
df['water_use_all_kgal'] = pd.to_numeric(df['water_use_all_kgal'], errors='coerce')
df['crime_score_5mi_weighted'] = pd.to_numeric(df['crime_score_5mi_weighted'], errors='coerce')

# Read your new coordinate columns and map them to standard names
df['latitude'] = pd.to_numeric(df['y_lat'], errors='coerce')
df['longitude'] = pd.to_numeric(df['x_lon'], errors='coerce')

# Safely convert utility usage
df['electric_use_kbtu'] = pd.to_numeric(df['electric_use_kbtu'], errors='coerce').fillna(0)
df['natural_gas_use_kbtu'] = pd.to_numeric(df['natural_gas_use_kbtu'], errors='coerce').fillna(0)
df['steam_use_kbtu'] = pd.to_numeric(df['steam_use_kbtu'], errors='coerce').fillna(0)
df['fuel_oil_02_use_kbtu'] = pd.to_numeric(df['fuel_oil_02_use_kbtu'], errors='coerce').fillna(0)

# Step A: Sum up all the energy the building used
df['calculated_total_energy'] = df['electric_use_kbtu'] + df['natural_gas_use_kbtu'] + df['steam_use_kbtu'] + df['fuel_oil_02_use_kbtu']

# Step B: Algebra! (SqFt = Total Energy / EUI)
df['estimated_sqft'] = df['calculated_total_energy'] / df['site_eui_kbtuft2'].replace(0, 0.0001)

# Step C: Fill the empty holes
df['total_floor_area_bld_pk_ft2'] = df['total_floor_area_bld_pk_ft2'].fillna(df['estimated_sqft'])

# Drop hopelessly broken rows
df = df.dropna(subset=['site_eui_kbtuft2', 'total_floor_area_bld_pk_ft2', 'primary_prop_type_epa_calc'])
df = df[df['total_floor_area_bld_pk_ft2'] > 0] 


# ---------------------------------------------------------
# NUANCE UPGRADE 1: Contextual Imputation
# ---------------------------------------------------------
df['total_ghg_emissions_mtco2e'] = df.groupby('primary_prop_type_epa_calc')['total_ghg_emissions_mtco2e'].transform(lambda x: x.fillna(x.median()))
df['water_use_all_kgal'] = df.groupby('primary_prop_type_epa_calc')['water_use_all_kgal'].transform(lambda x: x.fillna(x.median()))

# Fallback
df['total_ghg_emissions_mtco2e'] = df['total_ghg_emissions_mtco2e'].fillna(df['total_ghg_emissions_mtco2e'].median())
df['water_use_all_kgal'] = df['water_use_all_kgal'].fillna(df['water_use_all_kgal'].median())

# Engineer Metrics
df['ghg_per_sqft'] = df['total_ghg_emissions_mtco2e'] / df['total_floor_area_bld_pk_ft2']
df['water_per_sqft'] = df['water_use_all_kgal'] / df['total_floor_area_bld_pk_ft2']
df['eui'] = df['site_eui_kbtuft2']


# ---------------------------------------------------------
# NUANCE UPGRADE 2: Peer-to-Peer Percentile Ranking
# ---------------------------------------------------------
df['eui_score'] = 1 - df.groupby('primary_prop_type_epa_calc')['eui'].rank(pct=True)
df['ghg_score'] = 1 - df.groupby('primary_prop_type_epa_calc')['ghg_per_sqft'].rank(pct=True)
df['water_score'] = 1 - df.groupby('primary_prop_type_epa_calc')['water_per_sqft'].rank(pct=True)

# Rank crime score (invert so 1.0 is the safest)
df['crime_score'] = 1 - df['crime_score_5mi_weighted'].rank(pct=True)

# Handle cases where rank becomes NaN
df[['eui_score', 'ghg_score', 'water_score', 'crime_score']] = df[['eui_score', 'ghg_score', 'water_score', 'crime_score']].fillna(0.5)

# Calculate the Custom Composite Score using the WEIGHTS dictionary
df['composite_score'] = (
    (df['eui_score'] * SCORE_WEIGHTS['eui']) + 
    (df['ghg_score'] * SCORE_WEIGHTS['ghg']) + 
    (df['water_score'] * SCORE_WEIGHTS['water']) +
    (df['crime_score'] * SCORE_WEIGHTS['crime'])
)


# ---------------------------------------------------------
# NUANCE UPGRADE 3: Absolute Binning
# ---------------------------------------------------------
bins = [0.0, 0.20, 0.50, 0.80, 1.0]
labels = ['D', 'C', 'B', 'A']
df['Grade'] = pd.cut(df['composite_score'], bins=bins, labels=labels, include_lowest=True)

print("\nPeer-Adjusted Grade Distribution:")
print(df['Grade'].value_counts())

# Save the graded dataset for the web app
df.to_csv('philly_buildings_graded.csv', index=False)


# ---------------------------------------------------------
# THE MACHINE LEARNING PIPELINE
# ---------------------------------------------------------
print("\nPreparing ML Pipeline...")

# Define Features (X) and Target (y) using the mapped spatial columns
X = df[['year_built', 'total_floor_area_bld_pk_ft2', 'primary_prop_type_epa_calc', 'latitude', 'longitude']]
y = df['Grade']

# Split the data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Preprocessing Pipelines
numeric_features = ['year_built', 'total_floor_area_bld_pk_ft2', 'latitude', 'longitude']
numeric_transformer = SimpleImputer(strategy='median')

categorical_features = ['primary_prop_type_epa_calc']
categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='constant', fill_value='Unknown')),
    ('onehot', OneHotEncoder(handle_unknown='ignore'))
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        ('cat', categorical_transformer, categorical_features)
    ])

# Train Random Forest
model_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')) 
])

print("Training the AI Model...")
model_pipeline.fit(X_train, y_train)

# Evaluate
print("\nEvaluating Model Accuracy on Test Data:")
y_pred = model_pipeline.predict(X_test)
print(classification_report(y_test, y_pred))

# Export Model
joblib.dump(model_pipeline, 'property_rating_model.pkl')
print("\nSuccess! Model saved as 'property_rating_model.pkl'")