# Nexus Analytics — Sales Data Analysis & Prediction

**Multi-page editorial analytics app** built with Flask, Pandas, NumPy, Scikit-learn and Chart.js.

Modern light "editorial" UI — bold display type, coral/violet/teal data palette, crisp white
cards — split into six dedicated pages (Overview, Insights, Analysis, Forecasts, Explorer,
Data Control) with 15 chart modules, auto-generated insights, cross-page filters,
role-based access and ML-powered sales forecasting.

---

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Administrator | `admin` | `admin123` | Full (uploads, model ops, data control) |
| Analyst | `analyst` | `analyst123` | Dashboard + exports only |

---

## Project Structure

```
sales analyzer/
├── app.py                    # Flask backend: auth, 24 APIs, filters, exports
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (SECRET_KEY)
│
├── ml/                       # Machine Learning module
│   ├── train_model.py        # Linear Regression + time-series CV
│   ├── predict.py            # Single & multi-month forecasting
│   └── evaluate.py           # Model evaluation metrics
│
├── templates/
│   ├── base.html             # App shell: top nav + editorial page head
│   ├── login.html            # Split-layout login (story panel + form)
│   ├── overview.html         # KPI metrics dashboard
│   ├── insights.html         # AI signals + methodology
│   ├── analysis.html         # All interactive charts (trend, mix, seasonality)
│   ├── forecasts.html        # ML evaluation + forecast simulator
│   ├── explorer.html         # Raw data: search + pagination
│   ├── data_control.html     # Admin panel (upload, health, models)
│   ├── 404.html / 500.html   # Error pages
│
├── static/
│   ├── css/style.css         # Editorial design system (light theme)
│   └── js/
│       ├── app.js            # Core UI: nav, dropdowns, toasts, formatters
│       ├── dashboard.js      # 15 chart modules, filters, KPIs, forecasting
│       └── admin.js          # Drag-drop upload, retrain feedback
│
├── data/                     # cleaned_sales.csv, metrics.json, upload_log.json
├── models/                   # sales_model.pkl, scaler.pkl
└── uploads/                  # Temporary upload area
```

---

## Design System (Modern Editorial)

- Soft light-gray canvas (`#F8FAFC`), crisp white cards, thin borders, subtle shadows
- High-contrast ink (`#0E1626`) with Plus Jakarta Sans display type + Inter body
- Data palette: **coral** `#FF6B4A` · **violet** `#6D5EF7` · **teal** `#0FA3B1`
- Top navigation bar (sticky, blurred) with mobile drawer
- **Chart containers hard-capped** (290px / 330px / 210px) — graphs never stretch or overflow
- Numbered editorial section headers, eyebrow labels, reveal-on-scroll animation
- Loading skeletons on every async panel; reduced-motion support; fully responsive

---

## Pages (Multi-Page Application)

Each menu item is its own Flask route and Jinja2 template — no long-scrolling page.

| Route | Page | Contents |
|-------|------|----------|
| `/overview` | **Overview** | Hero highlights · global filters · KPI strip (trend badges + sparklines) · "Business at a glance" totals |
| `/insights` | **Insights** | 4 auto-generated signal cards (peak month, momentum, category leader, concentration) + methodology |
| `/analysis` | **Analysis** | Revenue trend · cumulative · category doughnut · regional bars · Pareto · year-over-year · growth pulse · distribution · scatter · profitability · seasonality heatmap |
| `/forecasts` | **Forecasts** | Model metrics (MAE/MAPE/R²), residual errors, forecast simulator, 6-month outlook |
| `/explorer` | **Explorer** | Paginated cleaned rows with debounced free-text search |
| `/data-control` | **Data Control** | Upload + cleaning log, dataset health, retrain/reset (admin role) |

Legacy aliases `/dashboard` → Overview and `/admin` → Data Control keep old bookmarks working.
Filters are persisted in `localStorage`, so applying them on one page carries over to the others.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | GET/POST | Authentication |
| `/overview` | GET | KPI metrics dashboard (auth) |
| `/insights` | GET | AI signals page (auth) |
| `/analysis` | GET | Interactive charts page (auth) |
| `/forecasts` | GET | Forecast lab page (auth) |
| `/explorer` | GET | Data explorer page (auth) |
| `/data-control` | GET | Data control panel (admin role) |
| `/dashboard`, `/admin` | GET | Legacy aliases for Overview / Data Control |
| `/admin/upload` | POST | Upload + clean CSV/XLSX |
| `/admin/retrain` | POST | Trigger model retraining |
| `/admin/reset` | POST | Delete data + models |
| `/api/metrics?…` | GET | KPI cards, trends, sparks, date range |
| `/api/insights?…` | GET | Auto-generated narrative insight cards |
| `/api/trend?…` | GET | Monthly revenue series |
| `/api/cumulative?…` | GET | Cumulative revenue + 3-month average |
| `/api/category?…` | GET | Category totals |
| `/api/region?…` | GET | Region totals |
| `/api/pareto?…` | GET | Top contributors + cumulative share |
| `/api/compare?…` | GET | Year-over-year monthly comparison |
| `/api/growth?…` | GET | Month-over-month growth rates (%) |
| `/api/distribution?…` | GET | Order-value histogram + quartile stats |
| `/api/scatter?…` | GET | Quantity vs Sales points by category |
| `/api/profitability?…` | GET | Sales, profit, margin% per category |
| `/api/heatmap?…` | GET | Category × Month matrix |
| `/api/filters` | GET | Distinct filter values |
| `/api/table?…` | GET | Paginated data rows (`&search=…` for free-text search) |
| `/api/model/metrics` | GET | Model evaluation metrics |
| `/api/forecast` | POST | Single forecast `{month, year}` |
| `/api/forecast/multiple` | POST | Multi-month forecast |
| `/api/forecast/residuals` | GET | Residual series |
| `/export/csv` | GET | Download filtered CSV |
| `/export/report` | GET | Download summary report |

All `/api/*` and `/export/*` endpoints accept filters:
`?region=North&category=Electronics&date_from=2024-01-01&date_to=2024-12-31`

---

## Data Format

Required columns (aliases auto-mapped):

| Column | Type | Example |
|--------|------|---------|
| Order Date | Date | 2024-01-15 |
| Category | String | Electronics |
| Region | String | North |
| Sales | Number | 1500.50 |
| Quantity | Number | 10 |
| Profit | Number (opt.) | 300.25 |

Datasets without optional columns (Region, Quantity, Profit) work fine — the related
charts (`region`, `scatter`, `profitability`) show a graceful placeholder instead of
failing. Upload `sample_sales_data.csv` to light up every chart at once.

---

## Machine Learning

- Linear Regression on monthly aggregates with feature engineering
  (time trend + cyclical month sin/cos)
- **Time-series cross-validation** (12-month min training window) → MAE, MSE, R², Train R², MAPE
- **Residual error chart** (actual − predicted per month)
- **Forecast Simulator** — pick month/year → animated result popup
- **6-month outlook** — animated timeline bars
- Auto-retrain on upload when ≥ 12 months of history are present

---

## Testing

```bash
python smoke_test.py
```

44 checks: all six page routes + legacy aliases, auth, roles, all analytics APIs,
dataset-aware endpoints, forecasts, filters, exports, validation, search.

---

## Tech Stack

Python · Flask · Pandas · NumPy · Scikit-learn · Matplotlib/Seaborn ·
Chart.js 4 · Custom CSS (editorial design system) · Vanilla JS
