import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

def train_and_save_model():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, 'crop_data.csv')
    model_path = os.path.join(current_dir, 'crop_model.joblib')
    
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Feature columns and target
    features = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
    X = df[features]
    y = df['label']
    
    print(f"Total samples: {len(df)}, Classes ({len(y.unique())}): {sorted(y.unique().tolist())}")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Train Random Forest Classifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model Accuracy on Test Set: {accuracy * 100:.2f}%")
    
    # Save model and metadata (feature names, classes)
    model_payload = {
        'model': clf,
        'features': features,
        'classes': list(clf.classes_),
        'accuracy': accuracy
    }
    joblib.dump(model_payload, model_path)
    print(f"Model saved successfully to {model_path}!")
    return accuracy

if __name__ == '__main__':
    train_and_save_model()
