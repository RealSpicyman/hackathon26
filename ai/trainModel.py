import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

print("Loading data...")
# 1. Load the data saved by fetch_data.py
df = pd.read_csv('ai/philly_buildings.csv')

# 2. Clean the Data
# Drop rows where critical size or energy data is missing
df = df.dropna(subset=['site_eui_kbtuft2', 'total_floor_area_bld_pk_ft2'])
df = df[df['total_floor_area_bld_pk_ft2'] > 0] # Prevent division by zero

# 3. Engineer the Metrics (Make them per square foot for fairness)
# Fill missing GHG and Water with the median so the math doesn't break
df['total_ghg_emissions_mtco2e'] = df['total_ghg_emissions_mtco2e'].fillna(df['total_ghg_emissions_mtco2e'].median())
df['water_use_all_kgal'] = df['water_use_all_kgal'].fillna(df['water_use_all_kgal'].median())

df['ghg_per_sqft'] = df['total_ghg_emissions_mtco2e'] / df['total_floor_area_bld_pk_ft2']
df['water_per_sqft'] = df['water_use_all_kgal'] / df['total_floor_area_bld_pk_ft2']

# 4. Normalize the Metrics (Scale them all between 0 and 1)
scaler = MinMaxScaler()
# We use EUI, GHG/sqft, and Water/sqft
metrics = ['site_eui_kbtuft2', 'ghg_per_sqft', 'water_per_sqft']
scaled_metrics = scaler.fit_transform(df[metrics])

# Invert the scales (so 1 is highly efficient, 0 is highly inefficient)
scaled_metrics = 1 - scaled_metrics

# 5. Calculate the Custom Composite Score
# 50% Energy (EUI), 30% Carbon (GHG), 20% Water
df['composite_score'] = (scaled_metrics[:, 0] * 0.50) + (scaled_metrics[:, 1] * 0.30) + (scaled_metrics[:, 2] * 0.20)

# 6. Assign Grades (A, B, C, D) based on percentiles
# top 20% get A, next 30% get B, next 30% get C, bottom 20% get D
df['Grade'] = pd.qcut(df['composite_score'], q=[0, 0.2, 0.5, 0.8, 1.0], labels=['D', 'C', 'B', 'A'])

print("\nGrade Distribution in Dataset:")
print(df['Grade'].value_counts())

# ---------------------------------------------------------
# THE MACHINE LEARNING PIPELINE
# ---------------------------------------------------------

# Define what the AI learns from (Features) and what it predicts (Target)
X = df[['year_built', 'total_floor_area_bld_pk_ft2', 'primary_prop_type_epa_calc']]
y = df['Grade']

# Split the data: 80% for training, 20% for testing
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Preprocessing: The AI only understands numbers. 
# We need to fill missing years and turn property types (Text) into numbers (One-Hot Encoding).
numeric_features = ['year_built', 'total_floor_area_bld_pk_ft2']
numeric_transformer = SimpleImputer(strategy='median')

categorical_features = ['primary_prop_type_epa_calc']
categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='constant', fill_value='Unknown')),
    ('onehot', OneHotEncoder(handle_unknown='ignore'))
])

# Combine the preprocessors
preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        ('cat', categorical_transformer, categorical_features)
    ])

# Create the full ML Pipeline (Preprocess -> Random Forest)
model_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
])

print("\nTraining the AI Model...")
model_pipeline.fit(X_train, y_train)

# Evaluate the AI
print("\nEvaluating Model Accuracy on Test Data:")
y_pred = model_pipeline.predict(X_test)
print(classification_report(y_test, y_pred))

# Save the trained model to a file so your web app can use it later
joblib.dump(model_pipeline, 'property_rating_model.pkl')
print("\nSuccess! Model saved as 'property_rating_model.pkl'")