"""
Sample Data Generator
=====================
Generates realistic, balanced sample sales data for testing the application.
Monthly row counts and category mix are balanced so the underlying
trend and seasonal patterns remain visible in aggregated monthly totals.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os


def generate_sample_data(num_months=24, orders_per_month=35, output_path='sample_sales_data.csv'):
    """
    Generate sample sales data for testing.

    Args:
        num_months (int): Number of months of data (default 24 = 2 years)
        orders_per_month (int): Orders generated per month (balanced)
        output_path (str): Path to save CSV file

    Returns:
        pandas.DataFrame: Generated data
    """
    np.random.seed(42)

    # Categories: base price (midpoint) and typical spread
    categories = {
        'Electronics': (1250, 350),
        'Furniture': (750, 200),
        'Office Supplies': (175, 60),
    }
    category_names = list(categories.keys())

    regions = ['North', 'South', 'East', 'West', 'Central']

    # Start at January 2022 for num_months
    start_year, start_month = 2022, 1

    data = []
    for m in range(num_months):
        # Current month/year
        year = start_year + (start_month - 1 + m) // 12
        month = (start_month - 1 + m) % 12 + 1

        # Trend: 3% growth per month; Seasonality: peak in June (+30%), trough in Dec (-30%)
        growth = 1.0 + 0.03 * m
        seasonality = 1.0 + 0.30 * np.sin(2 * np.pi * (month - 3) / 12)

        # Balanced category mix: rotate so every month has all 3 categories
        cat_order = category_names * ((orders_per_month // 3) + 1)
        cat_order = cat_order[:orders_per_month]
        np.random.shuffle(cat_order)

        # Days in month (avoid day 29-31 for February safety)
        days_in_month = 28

        for category in cat_order:
            midpoint, spread = categories[category]

            # Per-row price: normal around midpoint, clipped to realistic range
            base_price = np.clip(np.random.normal(midpoint, spread),
                                 midpoint - 2 * spread, midpoint + 2 * spread)

            sales = base_price * growth * seasonality
            quantity = max(1, int(sales / np.random.uniform(80, 150)))
            profit = sales * np.random.uniform(0.10, 0.30)
            region = np.random.choice(regions)
            day = np.random.randint(1, days_in_month + 1)

            data.append({
                'Order Date': f"{year}-{month:02d}-{day:02d}",
                'Category': category,
                'Region': region,
                'Sales': round(float(sales), 2),
                'Quantity': quantity,
                'Profit': round(float(profit), 2),
            })

    df = pd.DataFrame(data)

    # Introduce realistic imperfections:
    # 1. ~1.5% missing Quantity values
    n_missing = max(1, int(len(df) * 0.015))
    missing_idx = np.random.choice(df.index, n_missing, replace=False)
    df.loc[missing_idx, 'Quantity'] = None

    # 2. ~4% duplicate rows
    n_dupes = max(1, int(len(df) * 0.04))
    dupe_rows = df.sample(n=n_dupes, random_state=42)
    df = pd.concat([df, dupe_rows], ignore_index=True)

    # Shuffle
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Save
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df)} rows of sample data ({num_months} months x {orders_per_month} orders)")
    print(f"Saved to: {output_path}")
    print(f"\nData Summary:")
    print(f"  Date range: {df['Order Date'].min()} to {df['Order Date'].max()}")
    print(f"  Categories: {df['Category'].nunique()}")
    print(f"  Regions: {df['Region'].nunique()}")
    print(f"  Total Sales: ${df['Sales'].sum():,.2f}")
    print(f"  Missing Quantity values: {df['Quantity'].isna().sum()}")
    print(f"  Duplicate rows: {df.duplicated().sum()}")

    return df


def generate_minimal_sample():
    """Generate a small sample for quick testing (18 months)."""
    return generate_sample_data(num_months=18, orders_per_month=20,
                                output_path='sample_sales_data.csv')


if __name__ == '__main__':
    print("=" * 60)
    print("Sales Data Generator")
    print("=" * 60)

    choice = input("\n1. Generate full sample (24 months, ~840 rows)\n"
                   "2. Generate minimal sample (18 months, quick test)\n"
                   "Choice (1 or 2): ")

    if choice == '2':
        generate_minimal_sample()
    else:
        generate_sample_data()

    print("\n" + "=" * 60)
    print("Done! You can now upload 'sample_sales_data.csv' to the app.")
    print("=" * 60)
