"""
Model Evaluation Script
=======================
Evaluates the trained model and provides detailed metrics.
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    mean_absolute_percentage_error
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'cleaned_sales.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sales_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'models', 'scaler.pkl')
METRICS_PATH = os.path.join(BASE_DIR, 'data', 'metrics.json')


def evaluate_model(data_path=None):
    """
    Evaluate the trained model on test data.
    
    Args:
        data_path (str): Path to cleaned data file
    
    Returns:
        dict: Evaluation metrics or None if evaluation fails
    """
    if data_path is None:
        data_path = DATA_PATH
    
    try:
        # Check files exist
        if not os.path.exists(data_path):
            print(f"Data file not found: {data_path}")
            return None
        
        if not os.path.exists(MODEL_PATH):
            print(f"Model file not found: {MODEL_PATH}")
            return None
        
        # Load data, model, and scaler
        df = pd.read_csv(data_path)
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
        with open(SCALER_PATH, 'rb') as f:
            scaler = pickle.load(f)
        
        # Prepare features
        df['Order Date'] = pd.to_datetime(df['Order Date'])
        df['month_num'] = df['Order Date'].dt.month
        df['year'] = df['Order Date'].dt.year
        
        # Aggregate by month
        monthly_sales = df.groupby(['month_num', 'year']).agg(
            total_sales=('Sales', 'sum')
        ).reset_index()
        
        monthly_sales = monthly_sales.sort_values(['year', 'month_num'])
        
        # Feature engineering (must match training)
        monthly_sales['month_sin'] = np.sin(2 * np.pi * monthly_sales['month_num'] / 12)
        monthly_sales['month_cos'] = np.cos(2 * np.pi * monthly_sales['month_num'] / 12)
        origin_year = int(monthly_sales['year'].min())
        origin_month = int(monthly_sales.loc[monthly_sales['year'] == origin_year, 'month_num'].min())
        monthly_sales['time_index'] = (
            (monthly_sales['year'] - origin_year) * 12 + (monthly_sales['month_num'] - origin_month)
        )

        feature_cols = ['time_index', 'month_sin', 'month_cos']
        
        # Split data (same as training)
        X = monthly_sales[feature_cols].values
        y = monthly_sales['total_sales'].values
        
        split_idx = int(len(X) * 0.8)
        X_test = X[split_idx:]
        y_test = y[split_idx:]
        
        if len(X_test) == 0:
            print("No test data available")
            return None
        
        # Scale and predict
        X_test_scaled = scaler.transform(X_test)
        y_pred = model.predict(X_test_scaled)
        
        # Calculate metrics
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_test, y_pred)
        
        # MAPE (avoid division by zero)
        mask = y_test != 0
        if mask.sum() > 0:
            mape = mean_absolute_percentage_error(y_test[mask], y_pred[mask]) * 100
        else:
            mape = 0
        
        # Calculate residuals
        residuals = y_test - y_pred
        mae_absolute = np.mean(np.abs(residuals))
        
        # Metrics dictionary
        metrics = {
            'mae': round(float(mae), 2),
            'mse': round(float(mse), 2),
            'rmse': round(float(rmse), 2),
            'r2': round(float(r2), 4),
            'mape': round(float(mape), 2),
            'mean_residual': round(float(np.mean(residuals)), 2),
            'std_residual': round(float(np.std(residuals)), 2),
            'test_samples': int(len(y_test)),
            'evaluated_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Add per-sample predictions for detailed analysis
        predictions_detail = []
        for i in range(len(y_test)):
            predictions_detail.append({
                'actual': round(float(y_test[i]), 2),
                'predicted': round(float(y_pred[i]), 2),
                'residual': round(float(residuals[i]), 2),
                'month': int(X_test[i][0]),
                'year': int(X_test[i][1])
            })
        
        metrics['predictions_detail'] = predictions_detail
        
        return metrics
    
    except Exception as e:
        print(f"Error during evaluation: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def generate_evaluation_report(metrics):
    """
    Generate a formatted evaluation report.
    
    Args:
        metrics (dict): Evaluation metrics
    
    Returns:
        str: Formatted report
    """
    if metrics is None:
        return "No metrics available"
    
    report = """
╔══════════════════════════════════════════════════════════╗
║           MODEL EVALUATION REPORT                        ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Model Performance Metrics:                              ║
║  ─────────────────────────                               ║
║  Mean Absolute Error (MAE):    ${mae:>12,.2f}           ║
║  Mean Squared Error (MSE):     ${mse:>12,.2f}           ║
║  Root Mean Squared Error:      ${rmse:>12,.2f}           ║
║  R² Score:                     {r2:>12.4f}              ║
║  Mean Abs % Error (MAPE):      {mape:>11.2f}%           ║
║                                                          ║
║  Test Data:                                              ║
║  ─────────                                               ║
║  Test Samples:                   {test_samples:>6}        ║
║  Evaluated:                      {evaluated_at}           ║
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║  Interpretation:                                         ║
║  ───────────────                                         """.format(**metrics)
    
    # Add interpretation based on R² score
    r2 = metrics.get('r2', 0)
    if r2 >= 0.9:
        interpretation = "Excellent - Model explains variance very well"
    elif r2 >= 0.7:
        interpretation = "Good - Model explains most variance"
    elif r2 >= 0.5:
        interpretation = "Fair - Model has moderate predictive power"
    else:
        interpretation = "Poor - Model needs improvement"
    
    report += f"""
║  R² Interpretation: {interpretation:<39}║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """
    
    return report


def save_evaluation(metrics, filepath=None):
    """
    Save evaluation metrics to JSON file.
    
    Args:
        metrics (dict): Evaluation metrics
        filepath (str): Path to save file
    
    Returns:
        bool: True if successful
    """
    if filepath is None:
        filepath = METRICS_PATH
    
    try:
        with open(filepath, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"Metrics saved to: {filepath}")
        return True
    except Exception as e:
        print(f"Error saving metrics: {str(e)}")
        return False


def load_evaluation(filepath=None):
    """
    Load evaluation metrics from JSON file.
    
    Args:
        filepath (str): Path to metrics file
    
    Returns:
        dict: Evaluation metrics or None
    """
    if filepath is None:
        filepath = METRICS_PATH
    
    try:
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r') as f:
            metrics = json.load(f)
        
        return metrics
    except Exception as e:
        print(f"Error loading metrics: {str(e)}")
        return None


if __name__ == '__main__':
    # Run evaluation
    print("Evaluating model...")
    metrics = evaluate_model()
    
    if metrics:
        # Print report
        print(generate_evaluation_report(metrics))
        
        # Save metrics
        save_evaluation(metrics)
    else:
        print("Evaluation failed or no model available.")
