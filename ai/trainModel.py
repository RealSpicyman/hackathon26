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

print("Loading data...")
# 1. Load the data saved by fetch_data.py
# on_bad_lines='skip' tells Pandas to just throw away any row that has extra/stray commas
df = pd.read_csv('ai/philly_buildings.csv', on_bad_lines='skip')

df.columns = df.columns.str.strip()

# 1. Clean the Data
# Force all columns to be numeric
df['total_floor_area_bld_pk_ft2'] = pd.to_numeric(df['total_floor_area_bld_pk_ft2'], errors='coerce')
df['site_eui_kbtuft2'] = pd.to_numeric(df['site_eui_kbtuft2'], errors='coerce')
df['total_ghg_emissions_mtco2e'] = pd.to_numeric(df['total_ghg_emissions_mtco2e'], errors='coerce')
df['water_use_all_kgal'] = pd.to_numeric(df['water_use_all_kgal'], errors='coerce')

# Safely convert utility usage, filling missing utilities with 0 (since they probably don't use that utility)
df['electric_use_kbtu'] = pd.to_numeric(df['electric_use_kbtu'], errors='coerce').fillna(0)
df['natural_gas_use_kbtu'] = pd.to_numeric(df['natural_gas_use_kbtu'], errors='coerce').fillna(0)
df['steam_use_kbtu'] = pd.to_numeric(df['steam_use_kbtu'], errors='coerce').fillna(0)
df['fuel_oil_02_use_kbtu'] = pd.to_numeric(df['fuel_oil_02_use_kbtu'], errors='coerce').fillna(0)


# Step A: Sum up all the energy the building used
df['calculated_total_energy'] = df['electric_use_kbtu'] + df['natural_gas_use_kbtu'] + df['steam_use_kbtu'] + df['fuel_oil_02_use_kbtu']

# Step B: Algebra! (SqFt = Total Energy / EUI). 
# We replace EUI of 0 with 0.0001 just to prevent computer "division by zero" crashes.
df['estimated_sqft'] = df['calculated_total_energy'] / df['site_eui_kbtuft2'].replace(0, 0.0001)

# Step C: Fill the empty holes! If the city didn't provide sqft, plug in our mathematically estimated sqft.
df['total_floor_area_bld_pk_ft2'] = df['total_floor_area_bld_pk_ft2'].fillna(df['estimated_sqft'])
# ---------------------------------------------------------

# Now we run the dropna. It will only drop buildings that are completely, hopelessly broken.
df = df.dropna(subset=['site_eui_kbtuft2', 'total_floor_area_bld_pk_ft2', 'primary_prop_type_epa_calc'])
df = df[df['total_floor_area_bld_pk_ft2'] > 0] # Prevent division by zero later





# ---------------------------------------------------------
# NUANCE UPGRADE 1: Contextual Imputation
# ---------------------------------------------------------
# Instead of filling missing data with the global median, we fill it 
# with the median of that SPECIFIC building type.
df['total_ghg_emissions_mtco2e'] = df.groupby('primary_prop_type_epa_calc')['total_ghg_emissions_mtco2e'].transform(lambda x: x.fillna(x.median()))
df['water_use_all_kgal'] = df.groupby('primary_prop_type_epa_calc')['water_use_all_kgal'].transform(lambda x: x.fillna(x.median()))

# Fallback: If a group was entirely empty, fill with global median
df['total_ghg_emissions_mtco2e'] = df['total_ghg_emissions_mtco2e'].fillna(df['total_ghg_emissions_mtco2e'].median())
df['water_use_all_kgal'] = df['water_use_all_kgal'].fillna(df['water_use_all_kgal'].median())

# Engineer Metrics to be per-square-foot
df['ghg_per_sqft'] = df['total_ghg_emissions_mtco2e'] / df['total_floor_area_bld_pk_ft2']
df['water_per_sqft'] = df['water_use_all_kgal'] / df['total_floor_area_bld_pk_ft2']
df['eui'] = df['site_eui_kbtuft2']

# ---------------------------------------------------------
# NUANCE UPGRADE 2: Peer-to-Peer Percentile Ranking
# ---------------------------------------------------------
# We rank buildings against their peers. rank(pct=True) gives a value from 0 to 1.
# Lower consumption is better, so we subtract from 1 (making 1.0 the most efficient).
df['eui_score'] = 1 - df.groupby('primary_prop_type_epa_calc')['eui'].rank(pct=True)
df['ghg_score'] = 1 - df.groupby('primary_prop_type_epa_calc')['ghg_per_sqft'].rank(pct=True)
df['water_score'] = 1 - df.groupby('primary_prop_type_epa_calc')['water_per_sqft'].rank(pct=True)

# Handle cases where a building type only has 1 instance (rank becomes NaN)
df[['eui_score', 'ghg_score', 'water_score']] = df[['eui_score', 'ghg_score', 'water_score']].fillna(0.5)

# Calculate the Custom Composite Score (0.0 to 1.0 scale)
df['composite_score'] = (df['eui_score'] * 0.50) + (df['ghg_score'] * 0.30) + (df['water_score'] * 0.20)

# ---------------------------------------------------------
# NUANCE UPGRADE 3: Absolute Binning
# ---------------------------------------------------------
# Because our composite score is already a mathematically sound percentile 
# from 0 to 1, we map them directly to absolute tiers instead of using qcut.
bins = [0.0, 0.20, 0.50, 0.80, 1.0]
labels = ['D', 'C', 'B', 'A']
df['Grade'] = pd.cut(df['composite_score'], bins=bins, labels=labels, include_lowest=True)

print("\nPeer-Adjusted Grade Distribution:")
print(df['Grade'].value_counts())

# Save the properly graded dataset so the web app can fetch actual grades later
df.to_csv('philly_buildings_graded.csv', index=False)

# ---------------------------------------------------------
# THE MACHINE LEARNING PIPELINE
# ---------------------------------------------------------

# Define Features (X) and Target (y)
X = df[['year_built', 'total_floor_area_bld_pk_ft2', 'primary_prop_type_epa_calc']]
y = df['Grade']

# Split the data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Preprocessing Pipelines
numeric_features = ['year_built', 'total_floor_area_bld_pk_ft2']
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
    # Added class_weight='balanced' to handle any uneven distribution of A/B/C/D
    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')) 
])

print("\nTraining the AI Model...")
model_pipeline.fit(X_train, y_train)

# Evaluate
print("\nEvaluating Model Accuracy on Test Data:")
y_pred = model_pipeline.predict(X_test)
print(classification_report(y_test, y_pred))

# Export Model
joblib.dump(model_pipeline, 'property_rating_model.pkl')
print("\nSuccess! Model saved as 'property_rating_model.pkl'")