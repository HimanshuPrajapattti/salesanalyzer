"""
Model Training Script
=====================
Trains a Linear Regression model on cleaned sales data.
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'cleaned_sales.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sales_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'models', 'scaler.pkl')
METRICS_PATH = os.path.join(BASE_DIR, 'data', 'metrics.json')


def train_model(data_path=None):
    """
    Train Linear Regression model on sales data.
    
    Features:
        - month_num: Month number (1-12)
        - year: Year of the sale
    
    Target:
        - total_sales: Sum of sales for that month
    
    Returns:
        bool: True if training successful, False otherwise
    """
    if data_path is None:
        data_path = DATA_PATH
    
    try:
        # Check if data file exists
        if not os.path.exists(data_path):
            print(f"Data file not found: {data_path}")
            return False
        
        # Load cleaned data
        df = pd.read_csv(data_path)
        
        # Ensure required columns exist
        if 'Order Date' not in df.columns or 'Sales' not in df.columns:
            print("Required columns missing: 'Order Date' or 'Sales'")
            return False
        
        # Parse dates
        df['Order Date'] = pd.to_datetime(df['Order Date'])
        
        # Extract month and year
        df['month_num'] = df['Order Date'].dt.month
        df['year'] = df['Order Date'].dt.year
        df['month_year'] = df['Order Date'].dt.strftime('%Y-%m')
        
        # Aggregate sales by month
        monthly_sales = df.groupby(['month_num', 'year', 'month_year']).agg(
            total_sales=('Sales', 'sum'),
            total_quantity=('Quantity', 'sum') if 'Quantity' in df.columns else ('Sales', 'count')
        ).reset_index()
        
        # Sort by date
        monthly_sales = monthly_sales.sort_values(['year', 'month_num']).reset_index(drop=True)
        
        print(f"Training data shape: {monthly_sales.shape}")
        print(f"Date range: {monthly_sales['year'].min()}-{monthly_sales['month_num'].min()} to {monthly_sales['year'].max()}-{monthly_sales['month_num'].max()}")
        
        # Check if we have enough data
        if len(monthly_sales) < 12:
            print(f"Insufficient data: only {len(monthly_sales)} months. Need at least 12.")
            return False
        
        # Prepare features and target
        # Feature engineering: cyclical month encoding (seasonality) + time trend
        # Using sin/cos avoids the discontinuity at Dec->Jan and removes
        # collinearity between month_num, year and time_index.
        monthly_sales['month_sin'] = np.sin(2 * np.pi * monthly_sales['month_num'] / 12)
        monthly_sales['month_cos'] = np.cos(2 * np.pi * monthly_sales['month_num'] / 12)
        # Trend feature: months elapsed since the first month in the dataset
        origin_year = int(monthly_sales['year'].min())
        origin_month = int(monthly_sales.loc[monthly_sales['year'] == origin_year, 'month_num'].min())
        monthly_sales['time_index'] = (
            (monthly_sales['year'] - origin_year) * 12 + (monthly_sales['month_num'] - origin_month)
        )

        feature_cols = ['time_index', 'month_sin', 'month_cos']
        X = monthly_sales[feature_cols].values
        y = monthly_sales['total_sales'].values

        # Scale features (fit on full data; CV below scales inside folds)
        scaler = StandardScaler()

        # --- Evaluation: Time-series cross-validation ---
        # Expanding-window walk-forward with a 12-month minimum training
        # window (a full seasonal cycle is needed to learn seasonality).
        cv_maes, cv_r2s = [], []
        min_train = 12
        test_size = max(2, len(X) // 6)
        n_folds = 0
        
        start = min_train
        while start + test_size <= len(X):
            X_tr, X_te = X[:start], X[start:start + test_size]
            y_tr, y_te = y[:start], y[start:start + test_size]
            
            sc = StandardScaler()
            X_tr_s = sc.fit_transform(X_tr)
            X_te_s = sc.transform(X_te)
            
            fold_model = LinearRegression()
            fold_model.fit(X_tr_s, y_tr)
            y_pred = fold_model.predict(X_te_s)
            
            cv_maes.append(mean_absolute_error(y_te, y_pred))
            if len(set(y_te)) > 1:
                cv_r2s.append(r2_score(y_te, y_pred))
            n_folds += 1
            start += test_size
        
        n_splits = n_folds
        mae = float(np.mean(cv_maes))
        mse = float(np.mean([m ** 2 for m in cv_maes]))
        rmse = float(np.sqrt(mse))
        r2 = float(np.mean(cv_r2s)) if cv_r2s else 0.0

        # --- Final model: train on ALL data for best future predictions ---
        X_scaled = scaler.fit_transform(X)
        model = LinearRegression()
        model.fit(X_scaled, y)
        
        y_pred_all = model.predict(X_scaled)
        train_r2 = r2_score(y, y_pred_all)
        
        # MAPE on full data
        mask = y != 0
        mape = float(np.mean(np.abs((y[mask] - y_pred_all[mask]) / y[mask])) * 100) if mask.sum() > 0 else 0
        
        # Save metrics
        metrics = {
            'mae': round(mae, 2),
            'mse': round(mse, 2),
            'rmse': round(rmse, 2),
            'r2': round(r2, 4),
            'train_r2': round(float(train_r2), 4),
            'mape': round(mape, 2),
            'cv_folds': n_splits,
            'test_samples': 0,
            'train_samples': len(y),
            'total_samples': len(y),
            'trained_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'features': feature_cols,
            'target': 'total_sales',
            'origin_year': origin_year,
            'origin_month': origin_month
        }
        
        # Save metrics to JSON
        os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
        with open(METRICS_PATH, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Save model and scaler
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(model, f)
        
        with open(SCALER_PATH, 'wb') as f:
            pickle.dump(scaler, f)
        
        print("\n" + "=" * 50)
        print("Model Training Complete!")
        print("=" * 50)
        print(f"Method:  Time-series CV ({n_splits} folds) + refit on all data")
        print(f"MAE:     {mae:.2f}")
        print(f"MSE:     {mse:.2f}")
        print(f"RMSE:    {rmse:.2f}")
        print(f"R² (CV): {r2:.4f}")
        print(f"R² (fit): {train_r2:.4f}")
        print(f"MAPE:    {mape:.2f}%")
        print("=" * 50)
        print(f"Model saved to: {MODEL_PATH}")
        print(f"Metrics saved to: {METRICS_PATH}")
        
        return True
    
    except Exception as e:
        print(f"Error during model training: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def get_feature_importance(model, feature_names):
    """
    Get feature importance from linear regression model.
    
    Returns:
        dict: Feature names mapped to their coefficients
    """
    if hasattr(model, 'coef_'):
        importance = dict(zip(feature_names, model.coef_))
        return dict(sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True))
    return {}


if __name__ == '__main__':
    # Run training directly
    success = train_model()
    if success:
        print("\nTraining completed successfully!")
    else:
        print("\nTraining failed!")
