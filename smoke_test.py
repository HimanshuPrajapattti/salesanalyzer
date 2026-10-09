"""Smoke test for the upgraded futuristic dashboard."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

app.config['TESTING'] = True
client = app.test_client()

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ''))


# ---- Public routes ----
r = client.get('/login')
check('GET /login', r.status_code == 200, str(r.status_code))

r = client.get('/')
check('GET / redirects to login', r.status_code == 302, str(r.status_code))

# ---- Login flow ----
r = client.post('/login', data={'username': 'admin', 'password': 'wrong'})
check('Bad login rejected', r.status_code == 200 and 'Invalid' in r.get_data(as_text=True))

r = client.post('/login', data={'username': 'admin', 'password': 'admin123'})
check('Admin login', r.status_code == 302, str(r.status_code))

# ---- Auth-protected pages ----
r = client.get('/dashboard')
check('GET /dashboard (legacy alias)', r.status_code == 200, str(r.status_code))

r = client.get('/admin')
check('GET /admin (legacy alias)', r.status_code == 200, str(r.status_code))

# ---- MPA pages: one route per menu item ----
for route in ['/overview', '/insights', '/analysis', '/forecasts', '/explorer']:
    r = client.get(route)
    check(f'GET {route}', r.status_code == 200, str(r.status_code))

r = client.get('/data-control')
check('GET /data-control (administrator)', r.status_code == 200, str(r.status_code))

# ---- Analytics APIs ----
# /api/region returns 404 when the active dataset has no Region column (by design)
for route in ['/api/metrics', '/api/trend', '/api/category',
              '/api/heatmap', '/api/filters', '/api/table', '/api/model/metrics',
              '/api/forecast/residuals']:
    r = client.get(route)
    check(f'GET {route}', r.status_code == 200, str(r.status_code))

r = client.get('/api/region')
import pandas as _pd
_df = _pd.read_csv('data/cleaned_sales.csv') if os.path.exists('data/cleaned_sales.csv') else _pd.DataFrame()
_expected = 200 if 'Region' in _df.columns else 404
check('GET /api/region (dataset-aware)', r.status_code == _expected,
      f"status={r.status_code}, Region col={'yes' if 'Region' in _df.columns else 'no'}")

# ---- Advanced analysis APIs ----
for route in ['/api/insights', '/api/compare', '/api/growth', '/api/cumulative',
              '/api/distribution', '/api/pareto']:
    r = client.get(route)
    check(f'GET {route}', r.status_code == 200, str(r.status_code))

# Dataset-aware endpoints (need Quantity / Profit columns)
for route, col in [('/api/scatter', 'Quantity'), ('/api/profitability', 'Profit')]:
    r = client.get(route)
    _exp = 200 if col in _df.columns else 404
    check(f'GET {route} ({col}-aware)', r.status_code == _exp,
          f"status={r.status_code}, {col} col={'yes' if col in _df.columns else 'no'}")

# Insights must return at least one narrative card
r = client.get('/api/insights')
_d = r.get_json() if r.status_code == 200 else {}
check('Insights payload has cards', len(_d.get('insights', [])) >= 1,
      f"{len(_d.get('insights', []))} cards")

# KPI payload now carries monthly-average + date-range metadata
r = client.get('/api/metrics')
_d = r.get_json() if r.status_code == 200 else {}
check('KPI payload has avg_month', 'avg_month' in _d and 'spark' in _d.get('avg_month', {}),
      f"months={_d.get('months')}")

# ---- Forecast APIs ----
r = client.post('/api/forecast', json={'month': 6, 'year': 2026})
d = r.get_json() if r.status_code == 200 else {}
check('POST /api/forecast', r.status_code == 200 and 'predicted_sales' in d,
      f"pred={d.get('predicted_sales')}")

r = client.post('/api/forecast/multiple', json={'months': 6})
d = r.get_json() if r.status_code == 200 else {}
check('POST /api/forecast/multiple', r.status_code == 200 and len(d.get('forecasts', [])) == 6,
      f"{len(d.get('forecasts', []))} months")

# ---- Filters ----
r = client.get('/api/metrics?category=Electronics')
check('Filtered /api/metrics', r.status_code == 200, str(r.status_code))

# ---- Explorer search ----
r = client.get('/api/table?search=electronics')
d = r.get_json() if r.status_code == 200 else {}
check('Search matches rows (case-insensitive)',
      r.status_code == 200 and d.get('total', 0) > 0, f"total={d.get('total')}")

r = client.get('/api/table?search=zzz-no-such-row')
d = r.get_json() if r.status_code == 200 else {}
check('Search with no matches -> 0 rows',
      r.status_code == 200 and d.get('total') == 0, f"total={d.get('total')}")

# ---- Exports ----
r = client.get('/export/csv')
check('GET /export/csv', r.status_code == 200 and 'text/csv' in r.content_type,
      r.content_type)

r = client.get('/export/report')
check('GET /export/report', r.status_code == 200, str(r.status_code))

# ---- Input validation ----
r = client.post('/api/forecast', json={'month': 13, 'year': 2026})
check('Invalid month rejected', r.status_code == 400, str(r.status_code))

# ---- Role-based access ----
c2 = app.test_client()
c2.post('/login', data={'username': 'analyst', 'password': 'analyst123'})
r = c2.get('/admin')
check('Analyst blocked from /admin', r.status_code == 302, str(r.status_code))

r = c2.get('/dashboard')
check('Analyst can view dashboard', r.status_code == 200, str(r.status_code))

# ---- Unauthenticated blocked ----
c3 = app.test_client()
r = c3.get('/dashboard')
check('Unauthenticated redirected', r.status_code == 302, str(r.status_code))

r = c3.get('/api/metrics')
check('Unauthenticated API blocked', r.status_code == 302, str(r.status_code))

# ---- Error pages ----
c4 = app.test_client()
c4.post('/login', data={'username': 'admin', 'password': 'admin123'})
r = c4.get('/nonexistent')
check('404 page renders', r.status_code == 404, str(r.status_code))

# ---- Summary ----
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print('\n' + '=' * 55)
print(f'{passed}/{total} tests passed' if passed == total else f'SOME FAILED: {passed}/{total}')
print('=' * 55)
sys.exit(0 if passed == total else 1)
