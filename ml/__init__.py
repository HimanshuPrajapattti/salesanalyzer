"""
Machine Learning Module for Sales Forecasting
==============================================
Implements Linear Regression for predicting future sales.
"""

from .train_model import train_model
from .predict import predict_sales, predict_multiple_months
from .evaluate import evaluate_model

__all__ = ['train_model', 'predict_sales', 'predict_multiple_months', 'evaluate_model']
