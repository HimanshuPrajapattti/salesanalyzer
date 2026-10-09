"""
Sales Data Analysis & Prediction - Futuristic Enterprise Dashboard
===================================================================
Flask backend with glassmorphism UI, interactive analytics,
advanced filtering, CSV export, and ML-powered forecasting.
"""

import os
import io
import csv
import json
import pickle
import ssl
import urllib.request
import urllib.error
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps

from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, send_file, Response
)
from dotenv import load_dotenv

load_dotenv()
load_dotenv('.env.local')

# ============================================================
# App Configuration
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DATA_FOLDER = os.path.join(BASE_DIR, 'data')
MODEL_FOLDER = os.path.join(BASE_DIR, 'models')

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'futuristic-sales-analyzer-secret')
app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    DATA_FOLDER=DATA_FOLDER,
    MODEL_FOLDER=MODEL_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB
    CLEANED_DATA=os.path.join(DATA_FOLDER, 'cleaned_sales.csv'),
    TRAINED_MODEL=os.path.join(MODEL_FOLDER, 'sales_model.pkl'),
    SCALER=os.path.join(MODEL_FOLDER, 'scaler.pkl'),
    METRICS=os.path.join(DATA_FOLDER, 'metrics.json'),
    UPLOAD_LOG=os.path.join(DATA_FOLDER, 'upload_log.json'),
    INSFORGE_PROJECT_ID=os.environ.get('INSFORGE_PROJECT_ID', ''),
    INSFORGE_PROJECT_NAME=os.environ.get('INSFORGE_PROJECT_NAME', 'sales analyzer'),
    INSFORGE_ORG_ID=os.environ.get('INSFORGE_ORG_ID', ''),
    INSFORGE_APPKEY=os.environ.get('INSFORGE_APPKEY', '956i9sus'),
    INSFORGE_REGION=os.environ.get('INSFORGE_REGION', 'ap-southeast'),
    INSFORGE_API_KEY=os.environ.get('INSFORGE_API_KEY', ''),
    INSFORGE_OSS_HOST=os.environ.get('INSFORGE_OSS_HOST', 'https://956i9sus.ap-southeast.insforge.app'),
    INSFORGE_BASE_URL=os.environ.get('INSFORGE_BASE_URL', 'https://956i9sus.ap-southeast.insforge.app'),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

for d in (UPLOAD_FOLDER, DATA_FOLDER, MODEL_FOLDER):
    os.makedirs(d, exist_ok=True)

# Demo credentials (use hashed DB creds in production)
ADMIN_USERS = {
    'admin': {'password': 'admin123', 'role': 'administrator'},
    'analyst': {'password': 'analyst123', 'role': 'analyst'},
}


# ============================================================
# Auth Decorators
# ============================================================
def login_required(f):
    """Require an authenticated session."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user'):
            flash('Please sign in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """Require administrator role."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if not user:
            flash('Please sign in to continue.', 'warning')
            return redirect(url_for('login'))
        if user.get('role') != 'administrator':
            flash('Administrator privileges required.', 'danger')
            return redirect(url_for('overview'))
        return f(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_insforge_status():
    """Return the app's current InsForge configuration and remote reachability state."""
    project_id = app.config.get('INSFORGE_PROJECT_ID', '')
    project_name = app.config.get('INSFORGE_PROJECT_NAME', 'sales analyzer')
    host = app.config.get('INSFORGE_OSS_HOST', '')
    api_key = app.config.get('INSFORGE_API_KEY', '')
    base_url = app.config.get('INSFORGE_BASE_URL', host)

    reachable = False
    http_status = None
    error = None

    if base_url:
        req = urllib.request.Request(base_url, headers={'User-Agent': 'SalesAnalyzer/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as response:
                http_status = getattr(response, 'status', None)
                reachable = True
        except urllib.error.HTTPError as exc:
            http_status = exc.code
            reachable = True
            try:
                exc.close()
            except Exception:
                pass
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'

    return {
        'connected': bool(project_id and host and api_key and reachable),
        'project_id': project_id,
        'project_name': project_name,
        'host': host,
        'region': app.config.get('INSFORGE_REGION', ''),
        'api_key_present': bool(api_key),
        'base_url': base_url,
        'reachable': reachable,
        'http_status': http_status,
        'error': error,
    }


# ============================================================
# Data Access Helpers
# ============================================================
def data_exists():
    return os.path.exists(app.config['CLEANED_DATA'])


def load_data(filters=None):
    """
    Load cleaned sales data, optionally applying filters.

    filters: dict with keys region, category, date_from, date_to
    Returns DataFrame or empty DataFrame.
    """
    if not data_exists():
        return pd.DataFrame()

    df = pd.read_csv(app.config['CLEANED_DATA'])

    if filters:
        if filters.get('region'):
            df = df[df['Region'] == filters['region']]
        if filters.get('category'):
            df = df[df['Category'] == filters['category']]
        if filters.get('date_from'):
            df = df[df['Order Date'] >= filters['date_from']]
        if filters.get('date_to'):
            df = df[df['Order Date'] <= filters['date_to']]

    return df


def parse_filters():
    """Extract filter params from the query string."""
    return {
        'region': request.args.get('region', ''),
        'category': request.args.get('category', ''),
        'date_from': request.args.get('date_from', ''),
        'date_to': request.args.get('date_to', ''),
    }


def compute_kpis(df):
    """
    Compute KPI summary cards incl. month-over-month trends.
    Defensive against datasets missing optional columns.
    """
    if df.empty:
        return None

    df = df.copy()
    df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
    df = df.dropna(subset=['Order Date'])
    if df.empty:
        return None

    df['Month-Year'] = df['Order Date'].dt.strftime('%Y-%m')

    # Ensure numeric columns exist
    for col in ['Sales', 'Quantity', 'Profit']:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    months = sorted(df['Month-Year'].unique())
    current = months[-1] if months else None
    previous = months[-2] if len(months) > 1 else None

    cur = df[df['Month-Year'] == current] if current else df
    prev = df[df['Month-Year'] == previous] if previous else pd.DataFrame()

    def pct(cur_val, prev_val):
        if prev_val is None or prev_val == 0:
            return None
        return round(((cur_val - prev_val) / abs(prev_val)) * 100, 1)

    # ---- Monthly aggregates: drive sparklines, averages, momentum ----
    monthly = df.groupby('Month-Year').agg(
        sales=('Sales', 'sum'),
        qty=('Quantity', 'sum'),
        orders=('Sales', 'size'),
        profit=('Profit', 'sum'),
    )
    monthly['aov'] = np.where(monthly['orders'] > 0, monthly['sales'] / monthly['orders'], 0)
    monthly['margin'] = np.where(monthly['sales'] > 0,
                                 monthly['profit'] / monthly['sales'] * 100, 0)
    recent = monthly.tail(12)

    def spark(col):
        """Last-12-month sparkline series for a monthly column."""
        return [round(float(v), 2) for v in recent[col].tolist()]

    cur_rev = float(cur['Sales'].sum())
    prev_rev = float(prev['Sales'].sum()) if not prev.empty else None
    cur_qty = int(cur['Quantity'].sum())
    prev_qty = int(prev['Quantity'].sum()) if not prev.empty else None
    cur_orders = len(cur)
    prev_orders = len(prev) if not prev.empty else None
    cur_aov = cur_rev / cur_orders if cur_orders else 0
    prev_aov = (prev_rev / prev_orders) if (prev_rev and prev_orders) else None

    kpis = {
        'revenue': {
            'value': cur_rev,
            'display': f"${cur_rev:,.0f}",
            'trend': pct(cur_rev, prev_rev),
            'label': 'Revenue',
            'period': current,
            'spark': spark('sales'),
        },
        'quantity': {
            'value': cur_qty,
            'display': f"{cur_qty:,}",
            'trend': pct(cur_qty, prev_qty),
            'label': 'Units Sold',
            'period': current,
            'spark': spark('qty'),
        },
        'orders': {
            'value': cur_orders,
            'display': f"{cur_orders:,}",
            'trend': pct(cur_orders, prev_orders),
            'label': 'Orders',
            'period': current,
            'spark': spark('orders'),
        },
        'aov': {
            'value': cur_aov,
            'display': f"${cur_aov:,.2f}",
            'trend': pct(cur_aov, prev_aov),
            'label': 'Avg Order Value',
            'period': current,
            'spark': spark('aov'),
        },
        'total_revenue': float(df['Sales'].sum()),
        'total_quantity': int(df['Quantity'].sum()),
        'total_orders': len(df),
        'rows': len(df),
        'months': int(len(monthly)),
        'date_range': {
            'from': str(df['Order Date'].min())[:10],
            'to': str(df['Order Date'].max())[:10],
        },
    }

    # 5th KPI — average monthly revenue, trended last-3 vs prior-3 months
    avg_month_val = kpis['total_revenue'] / max(1, len(monthly))
    if len(monthly) >= 6:
        last3 = float(monthly['sales'].tail(3).mean())
        prev3 = float(monthly['sales'].iloc[-6:-3].mean())
        avg_trend = pct(last3, prev3)
    else:
        avg_trend = None

    kpis['avg_month'] = {
        'value': avg_month_val,
        'display': f"${avg_month_val:,.0f}",
        'trend': avg_trend,
        'label': 'Avg Monthly Revenue',
        'period': f"{len(monthly)} months",
        'spark': spark('sales'),
    }

    if 'Profit' in df.columns:
        profit = float(df['Profit'].sum())
        kpis['profit'] = round(profit, 2)
        kpis['margin'] = round((profit / kpis['total_revenue']) * 100, 1) if kpis['total_revenue'] else 0

        cur_profit = float(cur['Profit'].sum())
        prev_profit = float(prev['Profit'].sum()) if not prev.empty else None
        kpis['margin_kpi'] = {
            'value': kpis['margin'],
            'display': f"{kpis['margin']}%",
            'trend': pct(cur_profit, prev_profit),
            'label': 'Profit Margin',
            'period': current,
            'spark': spark('margin'),
        }

    return kpis


def read_upload_log():
    if os.path.exists(app.config['UPLOAD_LOG']):
        with open(app.config['UPLOAD_LOG'], 'r') as f:
            return json.load(f)
    return []


def write_upload_log(entry):
    log = read_upload_log()
    log.insert(0, entry)
    with open(app.config['UPLOAD_LOG'], 'w') as f:
        json.dump(log[:50], f, indent=2)


# ============================================================
# Data Cleaning Pipeline
# ============================================================
def clean_sales_data(df):
    """
    Clean uploaded sales data with Pandas.

    Returns (cleaned_df, cleaning_log) where cleaning_log is an ordered
    list of steps performed with row counts.
    """
    df_clean = df.copy()
    log = []

    def step(msg, rows=None):
        log.append({'message': msg, 'rows': rows, 'time': datetime.now().strftime('%H:%M:%S')})

    step(f"Loaded dataset: {len(df_clean)} rows x {len(df_clean.columns)} columns")

    # 1. Standardise column names
    df_clean.columns = [str(c).strip() for c in df_clean.columns]
    step(f"Normalised column names: {', '.join(df_clean.columns[:8])}")

    # 2. Drop exact duplicates
    before = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    removed = before - len(df_clean)
    step(f"Removed {removed} duplicate rows", len(df_clean))

    # 3. Map alternate column names
    required = ['Order Date', 'Category', 'Region', 'Sales', 'Quantity']
    missing = [c for c in required if c not in df_clean.columns]
    aliases = {
        'Order Date': ['order_date', 'date', 'orderdate', 'order date'],
        'Category': ['category', 'product category', 'product'],
        'Region': ['region', 'zone', 'territory'],
        'Sales': ['sales', 'revenue', 'amount', 'total'],
        'Quantity': ['quantity', 'qty', 'units'],
        'Profit': ['profit', 'margin', 'gain'],
    }
    for col in list(missing):
        for alt in aliases.get(col, []):
            match = next((c for c in df_clean.columns if c.lower() == alt.lower()), None)
            if match:
                df_clean.rename(columns={match: col}, inplace=True)
                missing.remove(col)
                step(f"Mapped '{match}' -> '{col}'")
                break

    if missing:
        step(f"WARNING: missing required columns: {', '.join(missing)}")

    # 4. Parse dates
    if 'Order Date' in df_clean.columns:
        df_clean['Order Date'] = pd.to_datetime(df_clean['Order Date'], errors='coerce', format='mixed')
        bad = df_clean['Order Date'].isna().sum()
        if bad:
            df_clean.dropna(subset=['Order Date'], inplace=True)
        step(f"Parsed Order Date, dropped {bad} invalid dates", len(df_clean))

    # 5. Numeric coercion + fill
    for col in ['Sales', 'Quantity', 'Profit']:
        if col in df_clean.columns:
            before_null = pd.to_numeric(df_clean[col], errors='coerce').isna().sum()
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            fill_val = df_clean[col].median() if col != 'Profit' else 0
            df_clean[col].fillna(fill_val, inplace=True)
            if before_null:
                step(f"Filled {before_null} missing/invalid '{col}' values")

    # 6. Categorical fill
    for col in ['Category', 'Region']:
        if col in df_clean.columns:
            mode = df_clean[col].mode()
            fill = mode[0] if not mode.empty else 'Unknown'
            n = df_clean[col].isna().sum()
            df_clean[col].fillna(fill, inplace=True)
            if n:
                step(f"Filled {n} missing '{col}' values with '{fill}'")

    # 7. Drop non-positive sales/quantity
    if 'Sales' in df_clean.columns:
        before = len(df_clean)
        df_clean = df_clean[df_clean['Sales'] > 0]
        dropped = before - len(df_clean)
        if dropped:
            step(f"Removed {dropped} rows with non-positive Sales", len(df_clean))

    # 8. Derived columns
    if 'Order Date' in df_clean.columns and len(df_clean):
        df_clean['Order Date'] = pd.to_datetime(df_clean['Order Date'])
        df_clean['Month'] = df_clean['Order Date'].dt.month
        df_clean['Month Name'] = df_clean['Order Date'].dt.strftime('%b')
        df_clean['Year'] = df_clean['Order Date'].dt.year
        df_clean['Month-Year'] = df_clean['Order Date'].dt.strftime('%Y-%m')
        df_clean['Order Date'] = df_clean['Order Date'].dt.strftime('%Y-%m-%d')
        step("Added derived columns: Month, Year, Month-Year")

    step(f"Final dataset ready: {len(df_clean)} rows", len(df_clean))
    return df_clean.reset_index(drop=True), log


# ============================================================
# Routes: Auth
# ============================================================
@app.route('/')
def index():
    if session.get('user'):
        return redirect(url_for('overview'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user'):
        return redirect(url_for('overview'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        record = ADMIN_USERS.get(username)

        if record and record['password'] == password:
            session['user'] = {
                'username': username,
                'role': record['role'],
                'logged_in_at': datetime.now().isoformat(),
            }
            flash(f'Welcome back, {username}.', 'success')
            target = 'data_control' if record['role'] == 'administrator' else 'overview'
            return redirect(url_for(target))

        flash('Invalid credentials. Try admin/admin123.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Signed out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/api/insforge/status')
def insforge_status():
    """Expose whether the local app is configured against the linked InsForge project."""
    return jsonify(get_insforge_status())


# ============================================================
# Routes: Pages (Multi-Page Application)
# Every menu item is its own route + its own template.
# ============================================================
def page_context(**extra):
    """Template context shared by every dashboard page."""
    ctx = {
        'user': session['user'],
        'has_data': data_exists(),
        'has_model': os.path.exists(app.config['TRAINED_MODEL']),
    }
    ctx.update(extra)
    return ctx


@app.route('/dashboard')        # legacy alias — old bookmarks keep working
@app.route('/overview')
@login_required
def overview():
    """Overview: KPI metrics dashboard."""
    return render_template('overview.html', **page_context())


@app.route('/insights')
@login_required
def insights():
    """AI signals & key business findings."""
    return render_template('insights.html', **page_context())


@app.route('/analysis')
@login_required
def analysis():
    """Interactive charts: trend, category, region, comparisons."""
    return render_template('analysis.html', **page_context())


@app.route('/forecasts')
@login_required
def forecasts():
    """Linear Regression forecasting simulator + evaluation metrics."""
    return render_template('forecasts.html', **page_context())


@app.route('/explorer')
@login_required
def explorer():
    """Raw data explorer with search + pagination."""
    return render_template('explorer.html', **page_context())


@app.route('/admin')            # legacy alias — old bookmarks keep working
@app.route('/data-control')
@admin_required
def data_control():
    data_stats = None
    preview = None
    upload_log = read_upload_log()

    if data_exists():
        try:
            df = pd.read_csv(app.config['CLEANED_DATA'])
            preview = df.head(8).to_dict('records')
            data_stats = {
                'rows': len(df),
                'columns': len(df.columns),
                'size_kb': round(os.path.getsize(app.config['CLEANED_DATA']) / 1024, 1),
                'date_min': df['Order Date'].min() if 'Order Date' in df.columns else 'N/A',
                'date_max': df['Order Date'].max() if 'Order Date' in df.columns else 'N/A',
                'categories': int(df['Category'].nunique()) if 'Category' in df.columns else 0,
                'regions': int(df['Region'].nunique()) if 'Region' in df.columns else 0,
            }
        except Exception as e:
            flash(f'Could not read cleaned data: {e}', 'warning')

    model_ready = os.path.exists(app.config['TRAINED_MODEL'])
    metrics = None
    if os.path.exists(app.config['METRICS']):
        with open(app.config['METRICS']) as f:
            metrics = json.load(f)

    datasets_managed = len(read_upload_log())
    health = {
        'data': data_exists(),
        'model': model_ready,
        'metrics': metrics is not None,
        'uploads': datasets_managed,
        'python': f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    return render_template(
        'data_control.html',
        user=session['user'],
        data_stats=data_stats,
        preview=preview,
        upload_log=upload_log,
        metrics=metrics,
        health=health,
        last_cleaning=session.pop('last_cleaning', None),
    )


# ============================================================
# Routes: Admin Actions
# ============================================================
@app.route('/admin/upload', methods=['POST'])
@admin_required
def upload_file():
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('data_control'))

    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        flash('Invalid file. Upload CSV or Excel (.csv, .xlsx, .xls).', 'danger')
        return redirect(url_for('data_control'))

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        if filename.lower().endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)

        cleaned, cleaning_log = clean_sales_data(df)

        if cleaned.empty:
            flash('No valid rows after cleaning. Check required columns.', 'danger')
            return redirect(url_for('data_control'))

        cleaned.to_csv(app.config['CLEANED_DATA'], index=False)

        # Persist cleaning log for the admin UI
        session['last_cleaning'] = {
            'filename': filename,
            'original_rows': len(df),
            'final_rows': len(cleaned),
            'steps': cleaning_log,
            'at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        write_upload_log({
            'filename': filename,
            'original_rows': len(df),
            'final_rows': len(cleaned),
            'columns': list(cleaned.columns)[:12],
            'at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })

        # Auto-retrain if enough months present
        trained = False
        if 'Order Date' in cleaned.columns:
            months = cleaned['Month-Year'].nunique() if 'Month-Year' in cleaned.columns else 0
            if months >= 12:
                from ml.train_model import train_model
                trained = train_model(app.config['CLEANED_DATA'])

        flash(f'Cleaned {filename}: {len(df)} → {len(cleaned)} rows.', 'success')
        if trained:
            flash('ML model retrained automatically.', 'info')

        os.remove(filepath)

    except Exception as e:
        flash(f'Upload failed: {e}', 'danger')

    return redirect(url_for('data_control'))


@app.route('/admin/retrain', methods=['POST'])
@admin_required
def retrain_model():
    if not data_exists():
        flash('No cleaned dataset available. Upload data first.', 'warning')
        return redirect(url_for('data_control'))

    try:
        from ml.train_model import train_model
        ok = train_model(app.config['CLEANED_DATA'])
        if ok:
            flash('Model retrained successfully.', 'success')
        else:
            flash('Training failed — need at least 12 months of data.', 'danger')
    except Exception as e:
        flash(f'Training error: {e}', 'danger')

    return redirect(url_for('data_control'))


@app.route('/admin/reset', methods=['POST'])
@admin_required
def reset_data():
    """Delete cleaned data + trained model."""
    for path in (app.config['CLEANED_DATA'], app.config['TRAINED_MODEL'],
                 app.config['SCALER'], app.config['METRICS'], app.config['UPLOAD_LOG']):
        if os.path.exists(path):
            os.remove(path)
    flash('All datasets and models cleared.', 'info')
    return redirect(url_for('data_control'))


# ============================================================
# API: Analytics
# ============================================================
@app.route('/api/metrics')
@login_required
def api_metrics():
    df = load_data(parse_filters())
    kpis = compute_kpis(df)
    if kpis is None:
        return jsonify({'error': 'No data available'}), 404
    return jsonify(kpis)


@app.route('/api/filters')
@login_required
def api_filters():
    """Distinct values for the filter dropdowns."""
    df = load_data()
    if df.empty:
        return jsonify({'regions': [], 'categories': [], 'date_min': '', 'date_max': ''})
    return jsonify({
        'regions': sorted(df['Region'].dropna().unique().tolist()) if 'Region' in df.columns else [],
        'categories': sorted(df['Category'].dropna().unique().tolist()) if 'Category' in df.columns else [],
        'date_min': df['Order Date'].min() if 'Order Date' in df.columns else '',
        'date_max': df['Order Date'].max() if 'Order Date' in df.columns else '',
    })


@app.route('/api/trend')
@login_required
def api_trend():
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404

    df['Order Date'] = pd.to_datetime(df['Order Date'])
    trend = (df.groupby(df['Order Date'].dt.strftime('%Y-%m'))['Sales']
               .sum().reset_index())
    trend.columns = ['month', 'sales']
    trend = trend.sort_values('month').tail(24)

    return jsonify({
        'labels': trend['month'].tolist(),
        'values': [round(v, 2) for v in trend['sales'].tolist()],
    })


@app.route('/api/category')
@login_required
def api_category():
    df = load_data(parse_filters())
    if df.empty or 'Category' not in df.columns:
        return jsonify({'error': 'No category data'}), 404

    grouped = df.groupby('Category')['Sales'].sum().sort_values(ascending=False)
    palette = ['#06b6d4', '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#a855f7']

    return jsonify({
        'labels': grouped.index.tolist(),
        'values': [round(v, 2) for v in grouped.values.tolist()],
        'colors': [palette[i % len(palette)] for i in range(len(grouped))],
    })


@app.route('/api/region')
@login_required
def api_region():
    df = load_data(parse_filters())
    if df.empty or 'Region' not in df.columns:
        return jsonify({'error': 'No region data'}), 404

    grouped = df.groupby('Region')['Sales'].sum().sort_values(ascending=False)
    return jsonify({
        'labels': grouped.index.tolist(),
        'values': [round(v, 2) for v in grouped.values.tolist()],
    })


@app.route('/api/heatmap')
@login_required
def api_heatmap():
    """Month x Category matrix for the heatmap chart."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data'}), 404

    df['Order Date'] = pd.to_datetime(df['Order Date'])
    df['MonthName'] = df['Order Date'].dt.strftime('%b')

    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    cats = sorted(df['Category'].dropna().unique().tolist())

    matrix = []
    for cat in cats:
        row = []
        for m in months:
            total = df[(df['Category'] == cat) & (df['MonthName'] == m)]['Sales'].sum()
            row.append(round(float(total), 2))
        matrix.append({'category': cat, 'values': row})

    return jsonify({'months': months, 'series': matrix})


@app.route('/api/table')
@login_required
def api_table():
    """Paginated data rows for the on-page data explorer."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data'}), 404

    page = max(1, int(request.args.get('page', 1)))
    per_page = min(100, int(request.args.get('per_page', 25)))

    # Free-text search across every column (case-insensitive)
    search = (request.args.get('search', '') or '').strip()
    if search:
        try:
            mask = (df.astype(str)
                      .apply(lambda col: col.str.contains(search, case=False, na=False))
                      .any(axis=1))
            df = df[mask]
        except Exception:
            pass

    total = len(df)
    start = (page - 1) * per_page
    chunk = df.iloc[start:start + per_page]

    # Replace NaN/NaT with None so the payload is strict-JSON safe
    rows = json.loads(chunk.to_json(orient='records', date_format='iso'))

    return jsonify({
        'rows': rows,
        'total': total,
        'page': page,
        'pages': max(1, -(-total // per_page)),
    })


# ============================================================
# API: ML Model
# ============================================================
@app.route('/api/model/metrics')
@login_required
def api_model_metrics():
    if not os.path.exists(app.config['METRICS']):
        return jsonify({'error': 'Model not trained yet'}), 404
    with open(app.config['METRICS']) as f:
        return jsonify(json.load(f))


@app.route('/api/forecast', methods=['POST'])
@login_required
def api_forecast():
    if not os.path.exists(app.config['TRAINED_MODEL']):
        return jsonify({'error': 'Model not trained. Upload data first.'}), 404

    try:
        data = request.get_json(silent=True) or {}
        month = int(data.get('month', 1))
        year = int(data.get('year', datetime.now().year))

        if not (1 <= month <= 12):
            return jsonify({'error': 'Month must be 1-12'}), 400
        if not (2020 <= year <= 2035):
            return jsonify({'error': 'Year must be 2020-2035'}), 400

        from ml.predict import predict_sales
        prediction = predict_sales(month, year)
        if prediction is None:
            return jsonify({'error': 'Prediction failed. Retrain the model.'}), 500

        metrics = {}
        if os.path.exists(app.config['METRICS']):
            with open(app.config['METRICS']) as f:
                metrics = json.load(f)

        return jsonify({
            'predicted_sales': prediction,
            'month': month,
            'year': year,
            'month_name': datetime(year, month, 1).strftime('%B %Y'),
            'model_metrics': metrics,
        })
    except (ValueError, TypeError) as e:
        return jsonify({'error': f'Invalid input: {e}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/forecast/multiple', methods=['POST'])
@login_required
def api_forecast_multiple():
    if not os.path.exists(app.config['TRAINED_MODEL']):
        return jsonify({'error': 'Model not trained'}), 404

    try:
        data = request.get_json(silent=True) or {}
        months = min(24, int(data.get('months', 6)))
        start_month = int(data.get('start_month', datetime.now().month))
        start_year = int(data.get('start_year', datetime.now().year))

        from ml.predict import predict_multiple_months
        forecasts = predict_multiple_months(months, start_month, start_year)
        if not forecasts:
            return jsonify({'error': 'Forecast failed'}), 500

        return jsonify({'forecasts': forecasts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/forecast/residuals')
@login_required
def api_residuals():
    """Residual errors from the last training run."""
    if not os.path.exists(app.config['METRICS']):
        return jsonify({'error': 'No metrics'}), 404

    with open(app.config['METRICS']) as f:
        metrics = json.load(f)

    # Rebuild residuals from training data vs predictions
    if not data_exists():
        return jsonify({'error': 'No data'}), 404

    try:
        import pickle as _pickle
        with open(app.config['TRAINED_MODEL'], 'rb') as f:
            model = _pickle.load(f)
        with open(app.config['SCALER'], 'rb') as f:
            scaler = _pickle.load(f)

        from ml.predict import build_features, load_time_origin

        df = pd.read_csv(app.config['CLEANED_DATA'])
        df['Order Date'] = pd.to_datetime(df['Order Date'])
        monthly = df.groupby([df['Order Date'].dt.year.rename('year'),
                              df['Order Date'].dt.month.rename('month_num')])['Sales'].sum().reset_index()
        monthly = monthly.sort_values(['year', 'month_num'])

        origin_y, origin_m = load_time_origin()
        X = np.vstack([build_features(r.month_num, r.year, origin_y, origin_m)[0]
                       for r in monthly.itertuples()])
        y = monthly['Sales'].values
        preds = model.predict(scaler.transform(X))

        return jsonify({
            'labels': [f"{int(r.year)}-{int(r.month_num):02d}" for r in monthly.itertuples()],
            'actual': [round(float(v), 2) for v in y],
            'predicted': [round(float(v), 2) for v in preds],
            'residuals': [round(float(a - p), 2) for a, p in zip(y, preds)],
            'metrics': {k: metrics.get(k) for k in ('mae', 'mse', 'r2', 'train_r2', 'mape')},
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# API: Advanced Analysis (insights, comparisons, distributions)
# ============================================================
MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _monthly_series(df):
    """Sales summed per calendar month, sorted ascending (index = 'YYYY-MM')."""
    d = df.copy()
    d['Order Date'] = pd.to_datetime(d['Order Date'], errors='coerce')
    d = d.dropna(subset=['Order Date'])
    if d.empty:
        return pd.Series(dtype=float)
    return (d.groupby(d['Order Date'].dt.strftime('%Y-%m'))['Sales']
             .sum().sort_index())


@app.route('/api/insights')
@login_required
def api_insights():
    """Auto-generated narrative insight cards for the Signals section."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404

    insights = []
    monthly = _monthly_series(df)

    # 1. Peak month vs average
    if len(monthly):
        peak_key = monthly.idxmax()
        peak_val = float(monthly.max())
        avg_val = float(monthly.mean())
        try:
            peak_label = datetime.strptime(peak_key, '%Y-%m').strftime('%b %Y')
        except ValueError:
            peak_label = peak_key
        lift = round(((peak_val - avg_val) / avg_val) * 100, 1) if avg_val else 0
        insights.append({
            'icon': 'trophy', 'tone': 'good',
            'title': 'Peak month',
            'value': f"${peak_val:,.0f}",
            'body': f"{peak_label} landed {lift}% above the monthly average of "
                    f"${avg_val:,.0f}.",
        })

    # 2. 90-day momentum (last 3 months vs prior 3 months)
    if len(monthly) >= 6:
        last3 = float(monthly.tail(3).mean())
        prev3 = float(monthly.iloc[-6:-3].mean())
        change = round(((last3 - prev3) / prev3) * 100, 1) if prev3 else None
        direction = 'above' if (change or 0) >= 0 else 'below'
        insights.append({
            'icon': 'gauge',
            'tone': 'good' if (change or 0) >= 0 else 'bad',
            'title': '90-day momentum',
            'value': f"{change:+.1f}%" if change is not None else '—',
            'body': f"Recent 3-month run rate (${last3:,.0f}/mo) sits {direction} "
                    f"the prior quarter (${prev3:,.0f}/mo).",
        })

    # 3. Category leader
    if 'Category' in df.columns:
        grouped = df.groupby('Category')['Sales'].sum().sort_values(ascending=False)
        total = float(grouped.sum())
        if total and len(grouped):
            share = round(float(grouped.iloc[0]) / total * 100, 1)
            insights.append({
                'icon': 'crown', 'tone': 'info',
                'title': 'Category leader',
                'value': f"{share}%",
                'body': f"{grouped.index[0]} contributes {share}% of revenue "
                        f"across {len(grouped)} categories.",
            })

            # 4. Concentration risk
            top2 = round(float(grouped.head(2).sum()) / total * 100, 1)
            concentrated = top2 >= 70
            insights.append({
                'icon': 'pie-chart',
                'tone': 'warn' if concentrated else 'good',
                'title': 'Revenue concentration',
                'value': f"{top2}%",
                'body': (f"Top two categories hold {top2}% of revenue — a single "
                         f"category dip would bite hard."
                         if concentrated else
                         f"Top two categories hold {top2}% of revenue — a healthy, "
                         f"balanced mix."),
            })

    # 5. Dataset scale fallback
    if not insights:
        insights.append({
            'icon': 'database', 'tone': 'info',
            'title': 'Dataset loaded',
            'value': f"{len(df):,}",
            'body': f"{len(df):,} rows ready for analysis.",
        })

    return jsonify({'insights': insights, 'rows': len(df)})


@app.route('/api/compare')
@login_required
def api_compare():
    """Year-over-year monthly comparison (grouped bars)."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404

    d = df.copy()
    d['Order Date'] = pd.to_datetime(d['Order Date'], errors='coerce')
    d = d.dropna(subset=['Order Date'])
    d['year'] = d['Order Date'].dt.year
    d['month'] = d['Order Date'].dt.month
    years = sorted(int(y) for y in d['year'].unique())

    if len(years) < 2:
        return jsonify({'available': False, 'labels': MONTH_ABBR,
                        'datasets': [], 'years': years})

    datasets = []
    for year in years[-2:]:
        g = d[d['year'] == year].groupby('month')['Sales'].sum()
        datasets.append({
            'label': str(year),
            'values': [round(float(g.get(m, 0)), 2) for m in range(1, 13)],
        })

    return jsonify({'available': True, 'labels': MONTH_ABBR,
                    'datasets': datasets, 'years': years[-2:]})


@app.route('/api/growth')
@login_required
def api_growth():
    """Month-over-month growth rate (%) as diverging bars."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404

    monthly = _monthly_series(df)
    if len(monthly) < 2:
        return jsonify({'error': 'Need at least 2 months of data'}), 404

    growth = monthly.pct_change().mul(100).round(1)
    values = [None if pd.isna(v) else float(v) for v in growth.tolist()]
    valid = [v for v in values if v is not None]

    return jsonify({
        'labels': monthly.index.tolist(),
        'values': values,
        'positive': sum(1 for v in valid if v >= 0),
        'negative': sum(1 for v in valid if v < 0),
        'average': round(sum(valid) / len(valid), 2) if valid else 0,
        'best': round(max(valid), 1) if valid else 0,
        'worst': round(min(valid), 1) if valid else 0,
    })


@app.route('/api/cumulative')
@login_required
def api_cumulative():
    """Cumulative revenue curve with a 3-month moving average."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404

    monthly = _monthly_series(df)
    if monthly.empty:
        return jsonify({'error': 'No data available'}), 404

    cumulative = monthly.cumsum()
    ma = monthly.rolling(3).mean()

    return jsonify({
        'labels': monthly.index.tolist(),
        'values': [round(float(v), 2) for v in cumulative.tolist()],
        'average': [None if pd.isna(v) else round(float(v), 2) for v in ma.tolist()],
        'total': round(float(cumulative.iloc[-1]), 2),
    })


@app.route('/api/distribution')
@login_required
def api_distribution():
    """Histogram of order values plus dispersion statistics."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404

    vals = pd.to_numeric(df['Sales'], errors='coerce').dropna().values
    if len(vals) < 2:
        return jsonify({'error': 'Not enough rows to distribute'}), 404

    counts, edges = np.histogram(vals, bins=10)

    def fmt_bin(v):
        v = float(v)
        if abs(v) >= 1000:
            return f"{v / 1000:.1f}K"
        return f"{v:.0f}"

    return jsonify({
        'labels': [f"{fmt_bin(edges[i])}–{fmt_bin(edges[i + 1])}"
                   for i in range(len(counts))],
        'values': [int(c) for c in counts],
        'stats': {
            'min': round(float(np.min(vals)), 2),
            'max': round(float(np.max(vals)), 2),
            'mean': round(float(np.mean(vals)), 2),
            'median': round(float(np.median(vals)), 2),
            'p25': round(float(np.percentile(vals, 25)), 2),
            'p75': round(float(np.percentile(vals, 75)), 2),
            'std': round(float(np.std(vals)), 2),
        },
    })


@app.route('/api/pareto')
@login_required
def api_pareto():
    """Pareto view: top contributors + cumulative share of total revenue."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404

    source = next((c for c in ('Product', 'Sub-Category', 'Sub Category',
                               'Item', 'Region', 'Category')
                   if c in df.columns), None)
    if not source:
        return jsonify({'error': 'No grouping column available'}), 404

    grouped = (df.groupby(source)['Sales'].sum()
                 .sort_values(ascending=False).head(10))
    total = float(df['Sales'].sum()) or 1.0
    cumulative = (grouped.cumsum() / total * 100).round(1)

    return jsonify({
        'source': source,
        'labels': grouped.index.astype(str).tolist(),
        'values': [round(float(v), 2) for v in grouped.tolist()],
        'cumulative': [float(v) for v in cumulative.tolist()],
    })


@app.route('/api/scatter')
@login_required
def api_scatter():
    """Quantity vs Sales scatter points, grouped by category when available."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404
    if 'Quantity' not in df.columns:
        return jsonify({'error': 'No quantity data'}), 404

    d = df.copy()
    d['Quantity'] = pd.to_numeric(d['Quantity'], errors='coerce')
    d['Sales'] = pd.to_numeric(d['Sales'], errors='coerce')
    d = d.dropna(subset=['Quantity', 'Sales'])

    budget = 600
    series = []
    has_category = 'Category' in d.columns

    groups = d.groupby('Category') if has_category else [(None, d)]
    per_group = max(1, budget // max(1, len(list(d['Category'].unique())))) if has_category else budget

    for label, grp in groups:
        sample = grp if len(grp) <= per_group else grp.sample(per_group, random_state=42)
        series.append({
            'label': str(label) if label is not None else 'Orders',
            'points': [[round(float(q), 2), round(float(s), 2)]
                       for q, s in zip(sample['Quantity'], sample['Sales'])],
        })

    return jsonify({'series': series, 'has_category': has_category,
                    'points': sum(len(s['points']) for s in series)})


@app.route('/api/profitability')
@login_required
def api_profitability():
    """Sales, profit and margin% per category (requires Profit column)."""
    df = load_data(parse_filters())
    if df.empty:
        return jsonify({'error': 'No data available'}), 404
    if 'Profit' not in df.columns:
        return jsonify({'error': 'No profit data'}), 404

    d = df.copy()
    d['Sales'] = pd.to_numeric(d['Sales'], errors='coerce').fillna(0)
    d['Profit'] = pd.to_numeric(d['Profit'], errors='coerce').fillna(0)

    if 'Category' in d.columns:
        g = d.groupby('Category').agg(sales=('Sales', 'sum'),
                                      profit=('Profit', 'sum'))
        g = g.sort_values('sales', ascending=False)
    else:
        g = pd.DataFrame({'sales': [d['Sales'].sum()],
                          'profit': [d['Profit'].sum()]},
                         index=['All Sales'])

    margins = [round((p / s * 100), 1) if s else 0.0
               for s, p in zip(g['sales'], g['profit'])]

    return jsonify({
        'labels': g.index.astype(str).tolist(),
        'sales': [round(float(v), 2) for v in g['sales']],
        'profit': [round(float(v), 2) for v in g['profit']],
        'margins': margins,
        'total_margin': round(float(d['Profit'].sum()) / float(d['Sales'].sum()) * 100, 1)
                        if float(d['Sales'].sum()) else 0,
    })


# ============================================================
# API: Export
# ============================================================
@app.route('/export/csv')
@login_required
def export_csv():
    """Download the cleaned dataset as CSV (with current filters)."""
    df = load_data(parse_filters())
    if df.empty:
        flash('No data to export.', 'warning')
        return redirect(url_for('overview'))

    output = io.StringIO()
    df.to_csv(output, index=False)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=sales_export_{timestamp}.csv',
            'Content-Type': 'text/csv; charset=utf-8',
        },
    )


@app.route('/export/report')
@login_required
def export_report():
    """
    Download a lightweight HTML/CSV summary report.
    Generated server-side with Pandas (works without a headless browser).
    """
    df = load_data(parse_filters())
    if df.empty:
        flash('No data to export.', 'warning')
        return redirect(url_for('overview'))

    summary = []
    summary.append('Sales Data Analysis Report')
    summary.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    summary.append(f'Total Rows: {len(df)}')
    summary.append(f'Total Revenue: ${df["Sales"].sum():,.2f}')
    if 'Profit' in df.columns:
        summary.append(f'Total Profit: ${df["Profit"].sum():,.2f}')
    summary.append('')

    if 'Category' in df.columns:
        summary.append('--- Category Summary ---')
        for cat, grp in df.groupby('Category'):
            summary.append(f'{cat}: Sales=${grp["Sales"].sum():,.2f}, Orders={len(grp)}')
        summary.append('')

    if 'Region' in df.columns:
        summary.append('--- Region Summary ---')
        for reg, grp in df.groupby('Region'):
            summary.append(f'{reg}: Sales=${grp["Sales"].sum():,.2f}, Orders={len(grp)}')

    report = '\n'.join(summary)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    return Response(
        report,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment; filename=sales_report_{timestamp}.txt'},
    )


# ============================================================
# Error Handlers
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ============================================================
# Entry Point
# ============================================================
if __name__ == '__main__':
    debug = os.environ.get('FLASK_ENV', 'production') != 'production'
    port = int(os.environ.get('PORT', 5000))

    print("=" * 60)
    print("  Sales Analytics — Futuristic Enterprise Dashboard")
    print(f"  http://localhost:{port}")
    print(f"  Debug: {debug}")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=debug)
