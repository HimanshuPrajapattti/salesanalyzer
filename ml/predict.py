"""
Prediction Script
=================
Makes sales predictions using the trained Linear Regression model.
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sales_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'models', 'scaler.pkl')
METRICS_PATH = os.path.join(BASE_DIR, 'data', 'metrics.json')


def load_model_and_scaler():
    """
    Load the trained model and scaler from disk.

    Returns:
        tuple: (model, scaler) or (None, None) if not found
    """
    try:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
            return None, None

        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)

        with open(SCALER_PATH, 'rb') as f:
            scaler = pickle.load(f)

        return model, scaler

    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None, None


def build_features(month, year, origin_year=2022, origin_month=1):
    """
    Build the feature vector used during training.

    Features: time_index, month_sin, month_cos
    """
    month_sin = np.sin(2 * np.pi * month / 12)
    month_cos = np.cos(2 * np.pi * month / 12)
    time_index = (year - origin_year) * 12 + (month - origin_month)
    return np.array([[time_index, month_sin, month_cos]])


def load_time_origin():
    """Load the training time origin from metrics.json."""
    try:
        if os.path.exists(METRICS_PATH):
            with open(METRICS_PATH, 'r') as f:
                metrics = json.load(f)
            return int(metrics.get('origin_year', 2022)), int(metrics.get('origin_month', 1))
    except Exception:
        pass
    return 2022, 1


def predict_sales(month, year):
    """
    Predict sales for a specific month and year.
    
    Args:
        month (int): Month number (1-12)
        year (int): Year (e.g., 2025)
    
    Returns:
        float: Predicted sales value, or None if model not available
    """
    model, scaler = load_model_and_scaler()
    
    if model is None or scaler is None:
        return None
    
    try:
        # Validate inputs
        month = int(month)
        year = int(year)
        
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")

        # Prepare features using the training origin
        origin_year, origin_month = load_time_origin()
        features = build_features(month, year, origin_year, origin_month)

        # Scale features
        features_scaled = scaler.transform(features)
        
        # Make prediction
        prediction = model.predict(features_scaled)[0]
        
        # Ensure prediction is non-negative
        prediction = max(0, float(prediction))
        
        return round(prediction, 2)
    
    except Exception as e:
        print(f"Error making prediction: {str(e)}")
        return None


def predict_multiple_months(months_ahead=6, start_month=None, start_year=None):
    """
    Predict sales for multiple future months.
    
    Args:
        months_ahead (int): Number of months to forecast
        start_month (int): Starting month (1-12), defaults to current month
        start_year (int): Starting year, defaults to current year
    
    Returns:
        list: List of dictionaries with month, year, and predicted sales
    """
    model, scaler = load_model_and_scaler()
    
    if model is None or scaler is None:
        return []
    
    try:
        # Set defaults to current date
        now = datetime.now()
        if start_month is None:
            start_month = now.month
        if start_year is None:
            start_year = now.year
        
        # Validate inputs
        start_month = int(start_month)
        start_year = int(start_year)
        months_ahead = min(int(months_ahead), 24)  # Limit to 24 months
        
        if start_month < 1 or start_month > 12:
            raise ValueError("Start month must be between 1 and 12")
        
        forecasts = []
        current_month = start_month
        current_year = start_year
        origin_year, origin_month = load_time_origin()

        for _ in range(months_ahead):
            # Prepare features using training origin
            features = build_features(current_month, current_year, origin_year, origin_month)
            features_scaled = scaler.transform(features)
            
            # Make prediction
            prediction = model.predict(features_scaled)[0]
            prediction = max(0, float(prediction))
            
            # Get month name
            month_name = datetime(current_year, current_month, 1).strftime('%b %Y')
            month_full = datetime(current_year, current_month, 1).strftime('%B %Y')
            
            forecasts.append({
                'month': current_month,
                'year': current_year,
                'month_name': month_name,
                'month_full': month_full,
                'predicted_sales': round(prediction, 2)
            })
            
            # Move to next month
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
        
        return forecasts
    
    except Exception as e:
        print(f"Error making multi-month predictions: {str(e)}")
        return []


def get_prediction_with_confidence(month, year, confidence_interval=0.1):
    """
    Get prediction with a confidence interval.
    
    Note: Linear Regression doesn't natively provide confidence intervals.
    This is a simplified approximation.
    
    Args:
        month (int): Month number (1-12)
        year (int): Year
        confidence_interval (float): Confidence interval (0.1 = ±10%)
    
    Returns:
        dict: Prediction with lower and upper bounds
    """
    prediction = predict_sales(month, year)
    
    if prediction is None:
        return None
    
    return {
        'predicted_sales': prediction,
        'lower_bound': round(prediction * (1 - confidence_interval), 2),
        'upper_bound': round(prediction * (1 + confidence_interval), 2),
        'confidence': f"{(1 - 2 * confidence_interval) * 100:.0f}%",
        'month': month,
        'year': year,
        'month_name': datetime(year, month, 1).strftime('%B %Y')
    }


if __name__ == '__main__':
    # Example usage
    print("Testing prediction...")
    
    # Predict for next month
    now = datetime.now()
    next_month = now.month + 1 if now.month < 12 else 1
    next_year = now.year if now.month < 12 else now.year + 1
    
    result = predict_sales(next_month, next_year)
    if result is not None:
        print(f"Predicted sales for {next_month}/{next_year}: ${result:,.2f}")
    else:
        print("Model not available. Please train the model first.")
    
    # Multi-month forecast
    print("\n6-month forecast:")
    forecasts = predict_multiple_months(6)
    for f in forecasts:
        print(f"  {f['month_name']}: ${f['predicted_sales']:,.2f}")
