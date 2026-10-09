/**
 * Nexus Analytics — Dashboard controller
 * ------------------------------------------------------------
 * • KPI strip with trends + sparklines
 * • Auto-generated insight cards
 * • Revenue: trend, cumulative, category, region, Pareto
 * • Comparisons: year-over-year, growth pulse, distribution,
 *   quantity/sales scatter, profitability
 * • Seasonality heatmap, model metrics, residual errors
 * • Forecast simulator + 6-month outlook
 * • Global filters (no reload) + paginated data explorer
 */

(function () {
    'use strict';

    /* ============================================================
       Global state (filters persist across pages via localStorage)
       ============================================================ */
    const FILTER_KEY = 'nexus.filters';

    function loadStoredFilters() {
        try {
            const raw = JSON.parse(localStorage.getItem(FILTER_KEY));
            return (raw && typeof raw === 'object') ? raw : {};
        } catch (e) { return {}; }
    }

    function saveFilters() {
        try { localStorage.setItem(FILTER_KEY, JSON.stringify(state.filters)); } catch (e) { /* ignore */ }
    }

    const state = {
        filters: Object.assign(
            { region: '', category: '', date_from: '', date_to: '' },
            loadStoredFilters()
        ),
        charts: {},
        categoryVisibility: {},
        page: 1,
        perPage: 25,
        search: '',
    };

    const el = (id) => document.getElementById(id);

    /* ============================================================
       Editorial chart theme (light background)
       ============================================================ */
    const C = {
        coral: '#FF6B4A',
        violet: '#6D5EF7',
        teal: '#0FA3B1',
        amber: '#F5A524',
        pink: '#EC4899',
        green: '#12B76A',
        red: '#F04438',
        slate: '#94A3B8',
        text: '#5B6472',
        axis: '#A3ABB9',
        grid: 'rgba(15, 23, 32, 0.06)',
        ink: '#0E1626',
    };
    const PALETTE = [C.coral, C.violet, C.teal, C.amber, C.pink, C.green];
    const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    function applyChartDefaults() {
        if (typeof Chart === 'undefined') return;
        Chart.defaults.color = C.text;
        Chart.defaults.borderColor = C.grid;
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.font.size = 11.5;
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.boxWidth = 7;
        Chart.defaults.plugins.legend.labels.padding = 14;
        Chart.defaults.plugins.legend.labels.color = C.ink;
        // White tooltip tuned for light cards
        Chart.defaults.plugins.tooltip.backgroundColor = '#FFFFFF';
        Chart.defaults.plugins.tooltip.titleColor = C.ink;
        Chart.defaults.plugins.tooltip.bodyColor = '#3D4756';
        Chart.defaults.plugins.tooltip.borderColor = '#E8EAEF';
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.padding = 11;
        Chart.defaults.plugins.tooltip.cornerRadius = 10;
        Chart.defaults.plugins.tooltip.displayColors = true;
        Chart.defaults.plugins.tooltip.boxPadding = 5;
        Chart.defaults.plugins.tooltip.titleFont = { weight: '700', size: 12.5 };
        Chart.defaults.plugins.tooltip.shadow = '0 8px 24px rgba(14,22,38,0.12)';
        Chart.defaults.animation.duration = 650;
        Chart.defaults.animation.easing = 'easeOutQuart';
        // Charts must obey their (height-capped) container
        Chart.defaults.responsive = true;
        Chart.defaults.maintainAspectRatio = false;
    }

    function hexA(hex, a) {
        const n = parseInt(hex.slice(1), 16);
        return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
    }

    /** Vertical gradient fill for area charts */
    function gradientFill(ctx, color, peak = 340) {
        const g = ctx.createLinearGradient(0, 0, 0, peak);
        g.addColorStop(0, hexA(color, 0.24));
        g.addColorStop(1, hexA(color, 0.0));
        return g;
    }

    /** '2025-01' -> 'Jan 25' */
    function shortMonth(key) {
        const parts = String(key).split('-');
        if (parts.length < 2) return key;
        const mi = parseInt(parts[1], 10) - 1;
        return `${MONTHS_SHORT[mi] || parts[1]} ${String(parts[0]).slice(2)}`;
    }

    const truncate = (s, n = 12) =>
        String(s).length > n ? String(s).slice(0, n - 1) + '…' : String(s);

    /* ---------- Chart lifecycle ---------- */
    function clearEmpty(canvasId) {
        const canvas = document.getElementById(canvasId);
        const body = canvas?.parentElement;
        if (!canvas || !body) return;
        canvas.style.display = '';
        const ph = body.querySelector('.empty-mini');
        if (ph) ph.hidden = true;
    }

    /** Replace a chart with a friendly placeholder (canvas is preserved). */
    function showEmpty(canvasId, icon, msg) {
        const canvas = document.getElementById(canvasId);
        const body = canvas?.parentElement;
        if (!body) return;
        body.classList.add('loaded');
        canvas.style.display = 'none';
        let ph = body.querySelector('.empty-mini');
        if (!ph) {
            ph = document.createElement('div');
            ph.className = 'empty-mini';
            ph.style.cssText = 'height:100%;justify-content:center;text-align:center';
            body.appendChild(ph);
        }
        ph.hidden = false;
        ph.innerHTML = `<i data-lucide="${icon}"></i><p>${msg}</p>`;
        window.refreshIcons();
    }

    function upsert(key, canvasId, config) {
        const el = document.getElementById(canvasId);
        if (!el) return;
        clearEmpty(canvasId);
        if (state.charts[key]) state.charts[key].destroy();
        state.charts[key] = new Chart(el.getContext('2d'), config);
        el.parentElement?.classList.add('loaded');
    }

    function filterQS() {
        const p = new URLSearchParams();
        Object.entries(state.filters).forEach(([k, v]) => v && p.set(k, v));
        return p.toString();
    }

    /* ============================================================
       KPI STRIP
       ============================================================ */
    const KPI_META = [
        { key: 'revenue',  icon: 'dollar-sign',   accent: 'linear-gradient(90deg,#FF6B4A,#EC4899)', tint: 'rgba(255,107,74,.10)', color: '#FF6B4A' },
        { key: 'orders',   icon: 'shopping-cart', accent: 'linear-gradient(90deg,#6D5EF7,#0FA3B1)', tint: 'rgba(109,94,247,.10)', color: '#6D5EF7' },
        { key: 'quantity', icon: 'boxes',         accent: 'linear-gradient(90deg,#0FA3B1,#12B76A)', tint: 'rgba(15,163,177,.10)', color: '#0FA3B1' },
        { key: 'aov',      icon: 'receipt',       accent: 'linear-gradient(90deg,#F5A524,#FF6B4A)', tint: 'rgba(245,165,36,.12)', color: '#F5A524' },
        { key: 'dynamic',  icon: 'percent',       accent: 'linear-gradient(90deg,#12B76A,#0FA3B1)', tint: 'rgba(18,183,106,.10)', color: '#12B76A' },
    ];

    function trendBadge(pct) {
        if (pct === null || pct === undefined) {
            return `<span class="trend flat">— no prior period</span>`;
        }
        const up = pct >= 0;
        return `<span class="trend ${up ? 'up' : 'down'}">
            <i data-lucide="${up ? 'trending-up' : 'trending-down'}"></i>
            ${up ? '+' : ''}${pct}%
        </span>`;
    }

    async function loadKPIs() {
        const grid = document.getElementById('kpiGrid');
        if (!grid) return;
        try {
            const k = await fetchJSON(`/api/metrics?${filterQS()}`);

            // Hero highlights
            const heroTotal = el('heroTotal');
            const heroRows = el('heroRows');
            if (heroTotal) heroTotal.textContent = fmtCurrency(k.total_revenue || 0);
            if (heroRows) heroRows.textContent = fmtNumber(k.rows || 0);

            // 5th slot: profit margin when available, else monthly average
            const dynamic = k.margin_kpi || k.avg_month;

            grid.innerHTML = KPI_META.map((meta) => {
                const d = meta.key === 'dynamic' ? dynamic : k[meta.key];
                if (!d) return '';
                return `
                <div class="kpi-card"
                     style="--kpi-accent:${meta.accent};--kpi-tint:${meta.tint};--kpi-color:${meta.color}">
                    <div class="kpi-top">
                        <span class="kpi-label">${d.label}</span>
                        <span class="kpi-icon"><i data-lucide="${meta.icon}"></i></span>
                    </div>
                    <div class="kpi-value">${d.display}</div>
                    <div class="kpi-bottom">
                        ${trendBadge(d.trend)}
                        <span class="kpi-period">${d.period || ''}</span>
                    </div>
                    ${d.spark && d.spark.length > 1
                        ? `<canvas class="spark" id="spark-${meta.key}"></canvas>` : ''}
                </div>`;
            }).join('');

            // Sparklines
            KPI_META.forEach((meta) => {
                const d = meta.key === 'dynamic' ? dynamic : k[meta.key];
                if (!d?.spark || d.spark.length < 2) return;
                const canvas = document.getElementById(`spark-${meta.key}`);
                if (!canvas) return;
                const sKey = `spark-${meta.key}`;
                if (state.charts[sKey]) state.charts[sKey].destroy();
                state.charts[sKey] = new Chart(canvas.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: d.spark.map((_, i) => i),
                        datasets: [{
                            data: d.spark,
                            borderColor: meta.color,
                            borderWidth: 1.8,
                            fill: true,
                            backgroundColor: hexA(meta.color, 0.10),
                            tension: 0.42,
                            pointRadius: 0,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false }, tooltip: { enabled: false } },
                        scales: { x: { display: false }, y: { display: false } },
                        animation: { duration: 800 },
                    },
                });
            });

            // "Business at a glance" totals (Overview page)
            const glance = el('glanceGrid');
            if (glance) {
                const range = k.date_range
                    ? `${k.date_range.from} → ${k.date_range.to}` : '—';
                glance.innerHTML = `
                    <div class="stat-cell">
                        <span class="stat-val">${fmtCurrency(k.total_revenue || 0)}</span>
                        <span class="stat-lbl">Total revenue</span>
                    </div>
                    <div class="stat-cell">
                        <span class="stat-val">${fmtNumber(k.total_quantity || 0)}</span>
                        <span class="stat-lbl">Total units</span>
                    </div>
                    <div class="stat-cell">
                        <span class="stat-val">${fmtNumber(k.total_orders || 0)}</span>
                        <span class="stat-lbl">Total orders</span>
                    </div>
                    <div class="stat-cell">
                        <span class="stat-val">${k.profit != null ? fmtCurrency(k.profit) : '—'}</span>
                        <span class="stat-lbl">Total profit</span>
                    </div>
                    <div class="stat-cell">
                        <span class="stat-val">${k.margin != null ? k.margin + '%' : '—'}</span>
                        <span class="stat-lbl">Net margin</span>
                    </div>
                    <div class="stat-cell">
                        <span class="stat-val tiny">${k.months || '—'} months · ${range}</span>
                        <span class="stat-lbl">Coverage</span>
                    </div>`;
            }

            window.refreshIcons();
        } catch (err) {
            console.error('KPI load failed:', err);
            grid.innerHTML = `
                <div class="kpi-card" style="grid-column:1/-1;align-items:center;justify-content:center;text-align:center">
                    <span class="kpi-label">No data for current filters</span>
                    <p style="color:#7A8496;font-size:13px">Adjust or clear the filters to see KPIs.</p>
                </div>`;
        }
    }

    /* ============================================================
       01 · INSIGHT CARDS
       ============================================================ */
    async function loadInsights() {
        const grid = document.getElementById('insightGrid');
        if (!grid) return;
        try {
            const d = await fetchJSON(`/api/insights?${filterQS()}`);
            grid.innerHTML = (d.insights || []).map((ins) => `
                <div class="insight-card ${ins.tone || 'info'}">
                    <div class="insight-top">
                        <span class="insight-icon"><i data-lucide="${ins.icon}"></i></span>
                        <span class="insight-title">${ins.title}</span>
                    </div>
                    <span class="insight-value">${ins.value}</span>
                    <p class="insight-body">${ins.body}</p>
                </div>`).join('');
            window.refreshIcons();
        } catch (err) {
            console.error('Insights unavailable:', err);
            grid.innerHTML = `
                <div class="insight-card info" style="grid-column:1/-1">
                    <div class="insight-top">
                        <span class="insight-icon"><i data-lucide="info"></i></span>
                        <span class="insight-title">Insights</span>
                    </div>
                    <p class="insight-body">Not enough data to generate insights for the current filters.</p>
                </div>`;
            window.refreshIcons();
        }
    }

    /* ============================================================
       02 · REVENUE TREND
       ============================================================ */
    async function loadTrend() {
        try {
            const d = await fetchJSON(`/api/trend?${filterQS()}`);
            const canvas = document.getElementById('trendChart');
            const ctx = canvas?.getContext('2d');
            if (!ctx) return;

            const range = document.getElementById('trendRange');
            if (range) range.textContent = `${d.labels.length} months`;

            upsert('trend', 'trendChart', {
                type: 'line',
                data: {
                    labels: d.labels.map(shortMonth),
                    datasets: [{
                        label: 'Monthly Revenue',
                        data: d.values,
                        borderColor: C.coral,
                        backgroundColor: gradientFill(ctx, C.coral),
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.38,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: C.coral,
                        pointHoverBorderColor: '#FFFFFF',
                        pointHoverBorderWidth: 2,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (c) => ' Revenue: ' + fmtCurrency(c.parsed.y) } },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12, color: C.axis },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('trendChart', 'line-chart', 'No trend data for the current filters.');
        }
    }

    /* ============================================================
       02 · CUMULATIVE REVENUE
       ============================================================ */
    async function loadCumulative() {
        try {
            const d = await fetchJSON(`/api/cumulative?${filterQS()}`);
            const canvas = document.getElementById('cumulativeChart');
            const ctx = canvas?.getContext('2d');
            if (!ctx) return;

            upsert('cumulative', 'cumulativeChart', {
                type: 'line',
                data: {
                    labels: d.labels.map(shortMonth),
                    datasets: [
                        {
                            label: 'Cumulative',
                            data: d.values,
                            borderColor: C.violet,
                            backgroundColor: gradientFill(ctx, C.violet),
                            borderWidth: 2.5,
                            fill: true,
                            tension: 0.35,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                        },
                        {
                            label: '3-month avg',
                            data: d.average,
                            borderColor: C.coral,
                            borderWidth: 2,
                            borderDash: [5, 4],
                            fill: false,
                            tension: 0.35,
                            pointRadius: 0,
                            spanGaps: true,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14 } },
                        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${fmtCurrency(c.parsed.y)}` } },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 6, color: C.axis },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('cumulativeChart', 'trending-up', 'Cumulative view unavailable.');
        }
    }

    /* ============================================================
       02 · CATEGORY DOUGHNUT + TOGGLES
       ============================================================ */
    let categoryData = null;

    async function loadCategory() {
        try {
            const d = await fetchJSON(`/api/category?${filterQS()}`);
            categoryData = d;

            d.labels.forEach((l) => {
                if (!(l in state.categoryVisibility)) state.categoryVisibility[l] = true;
            });
            renderCategoryToggles();

            const values = d.labels.map((l, i) => (state.categoryVisibility[l] ? d.values[i] : 0));

            upsert('category', 'categoryChart', {
                type: 'doughnut',
                data: {
                    labels: d.labels,
                    datasets: [{
                        data: values,
                        backgroundColor: d.colors,
                        borderColor: '#FFFFFF',
                        borderWidth: 3,
                        hoverOffset: 12,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '64%',
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (c) => ` ${c.label}: ${fmtCurrency(c.parsed)}` } },
                    },
                },
            });
        } catch (err) {
            showEmpty('categoryChart', 'pie-chart', 'No category data in this dataset.');
        }
    }

    function renderCategoryToggles() {
        const wrap = document.getElementById('categoryToggles');
        if (!wrap || !categoryData) return;

        wrap.innerHTML = categoryData.labels.map((label, i) => `
            <button class="cat-toggle ${state.categoryVisibility[label] ? 'on' : 'off'}" data-cat="${label}">
                <span class="dot" style="background:${categoryData.colors[i]}"></span>
                ${label}
            </button>`).join('');

        wrap.querySelectorAll('.cat-toggle').forEach((btn) => {
            btn.addEventListener('click', () => {
                const cat = btn.dataset.cat;
                state.categoryVisibility[cat] = !state.categoryVisibility[cat];
                loadCategory();
            });
        });
    }

    /* ============================================================
       02 · REGION BARS
       ============================================================ */
    async function loadRegion() {
        try {
            const d = await fetchJSON(`/api/region?${filterQS()}`);

            upsert('region', 'regionChart', {
                type: 'bar',
                data: {
                    labels: d.labels,
                    datasets: [{
                        label: 'Revenue',
                        data: d.values,
                        backgroundColor: d.labels.map((_, i) => hexA(PALETTE[i % PALETTE.length], 0.85)),
                        borderColor: d.labels.map((_, i) => PALETTE[i % PALETTE.length]),
                        borderWidth: 1.5,
                        borderRadius: 8,
                        borderSkipped: false,
                        maxBarThickness: 40,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (c) => ' ' + fmtCurrency(c.parsed.x) } },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                        y: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { color: C.ink, font: { weight: '600' } },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('regionChart', 'map-off', 'Region column not present in this dataset.');
        }
    }

    /* ============================================================
       02 · PARETO (bars + cumulative %)
       ============================================================ */
    async function loadPareto() {
        try {
            const d = await fetchJSON(`/api/pareto?${filterQS()}`);
            const sub = document.getElementById('paretoSub');
            if (sub) sub.textContent = `Top ${d.labels.length} by ${d.source} + cumulative share`;

            upsert('pareto', 'paretoChart', {
                data: {
                    labels: d.labels.map((l) => truncate(l, 13)),
                    datasets: [
                        {
                            type: 'bar',
                            label: 'Revenue',
                            data: d.values,
                            backgroundColor: hexA(C.teal, 0.78),
                            borderColor: C.teal,
                            borderWidth: 1.5,
                            borderRadius: 7,
                            borderSkipped: false,
                            maxBarThickness: 40,
                            yAxisID: 'y',
                        },
                        {
                            type: 'line',
                            label: 'Cumulative %',
                            data: d.cumulative,
                            borderColor: C.violet,
                            backgroundColor: C.violet,
                            borderWidth: 2.2,
                            tension: 0.3,
                            pointRadius: 3,
                            pointHoverRadius: 5,
                            yAxisID: 'y1',
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14 } },
                        tooltip: {
                            callbacks: {
                                label: (c) => c.dataset.yAxisID === 'y1'
                                    ? ` Cumulative: ${c.parsed.y}%`
                                    : ` Revenue: ${fmtCurrency(c.parsed.y)}`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { color: C.axis, maxRotation: 40, minRotation: 0, font: { size: 10.5 } },
                        },
                        y: {
                            beginAtZero: true,
                            position: 'left',
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                        y1: {
                            beginAtZero: true,
                            max: 100,
                            position: 'right',
                            grid: { display: false },
                            border: { display: false },
                            ticks: { callback: (v) => v + '%', color: C.violet },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('paretoChart', 'bar-chart-2', 'No grouping column available for Pareto analysis.');
        }
    }

    /* ============================================================
       03 · YEAR-OVER-YEAR
       ============================================================ */
    async function loadCompare() {
        try {
            const d = await fetchJSON(`/api/compare?${filterQS()}`);
            const years = document.getElementById('compareYears');

            if (!d.available) {
                if (years) years.textContent = 'need 2 years';
                showEmpty('compareChart', 'git-compare',
                    'Two full years of data are required for a year-over-year comparison.');
                return;
            }
            if (years) years.textContent = d.years.join(' vs ');

            upsert('compare', 'compareChart', {
                type: 'bar',
                data: {
                    labels: d.labels,
                    datasets: d.datasets.map((ds, i) => ({
                        label: ds.label,
                        data: ds.values,
                        backgroundColor: i === 0 ? hexA(C.coral, 0.85) : hexA(C.violet, 0.55),
                        borderColor: i === 0 ? C.coral : C.violet,
                        borderWidth: 1.5,
                        borderRadius: 6,
                        borderSkipped: false,
                        maxBarThickness: 22,
                    })),
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14 } },
                        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${fmtCurrency(c.parsed.y)}` } },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { color: C.axis },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('compareChart', 'git-compare', 'Comparison unavailable for these filters.');
        }
    }

    /* ============================================================
       03 · GROWTH PULSE
       ============================================================ */
    async function loadGrowth() {
        try {
            const d = await fetchJSON(`/api/growth?${filterQS()}`);

            const box = document.getElementById('growthStats');
            if (box) {
                box.innerHTML = `
                    <div class="card-stat"><b>${d.average >= 0 ? '+' : ''}${d.average}%</b><span>Average</span></div>
                    <div class="card-stat"><b>+${d.best}%</b><span>Best</span></div>
                    <div class="card-stat"><b>${d.worst}%</b><span>Worst</span></div>`;
            }

            upsert('growth', 'growthChart', {
                type: 'bar',
                data: {
                    labels: d.labels.map(shortMonth),
                    datasets: [{
                        label: 'MoM growth %',
                        data: d.values,
                        backgroundColor: d.values.map((v) =>
                            v === null ? 'transparent' : (v >= 0 ? hexA(C.green, 0.8) : hexA(C.red, 0.8))),
                        borderColor: d.values.map((v) =>
                            v === null ? 'transparent' : (v >= 0 ? C.green : C.red)),
                        borderWidth: 1.4,
                        borderRadius: 5,
                        borderSkipped: false,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: { label: (c) => ` ${c.parsed.y === null ? '—' : c.parsed.y + '%'} vs prior month` },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { color: C.axis, maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10 } },
                        },
                        y: {
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => v + '%', color: C.axis },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('growthChart', 'activity', 'Need at least 2 months to compute growth.');
        }
    }

    /* ============================================================
       03 · ORDER DISTRIBUTION
       ============================================================ */
    async function loadDistribution() {
        try {
            const d = await fetchJSON(`/api/distribution?${filterQS()}`);
            const box = document.getElementById('distStats');
            if (box) {
                box.innerHTML = `
                    <div class="card-stat"><b>${fmtCurrency(d.stats.median)}</b><span>Median</span></div>
                    <div class="card-stat"><b>${fmtCurrency(d.stats.mean)}</b><span>Avg</span></div>
                    <div class="card-stat"><b>${fmtCompact(d.stats.std)}</b><span>σ Std dev</span></div>`;
            }

            upsert('dist', 'distChart', {
                type: 'bar',
                data: {
                    labels: d.labels,
                    datasets: [{
                        label: 'Orders',
                        data: d.values,
                        backgroundColor: hexA(C.teal, 0.78),
                        borderColor: C.teal,
                        borderWidth: 1.4,
                        borderRadius: 6,
                        borderSkipped: false,
                        maxBarThickness: 46,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => `Order value ${items[0].label}`,
                                label: (c) => ` ${c.parsed.y} orders`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { color: C.axis, maxRotation: 45, font: { size: 10 } },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { color: C.axis, precision: 0 },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('distChart', 'bar-chart', 'Distribution unavailable for these filters.');
        }
    }

    /* ============================================================
       03 · QUANTITY vs SALES SCATTER
       ============================================================ */
    async function loadScatter() {
        try {
            const d = await fetchJSON(`/api/scatter?${filterQS()}`);

            upsert('scatter', 'scatterChart', {
                type: 'scatter',
                data: {
                    datasets: d.series.map((s, i) => ({
                        label: s.label,
                        data: s.points.map((p) => ({ x: p[0], y: p[1] })),
                        backgroundColor: hexA(PALETTE[i % PALETTE.length], 0.55),
                        borderColor: PALETTE[i % PALETTE.length],
                        borderWidth: 1,
                        pointRadius: 3.5,
                        pointHoverRadius: 6,
                    })),
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: d.has_category,
                            position: 'bottom',
                            labels: { usePointStyle: true, padding: 12, font: { size: 11 } },
                        },
                        tooltip: {
                            callbacks: {
                                label: (c) => ` ${c.parsed.x} units · ${fmtCurrency(c.parsed.y)}`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            title: { display: true, text: 'Quantity', color: C.axis, font: { size: 11 } },
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { color: C.axis },
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Sales', color: C.axis, font: { size: 11 } },
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('scatterChart', 'scatter-chart', 'Quantity column not present in this dataset.');
        }
    }

    /* ============================================================
       03 · PROFITABILITY
       ============================================================ */
    async function loadProfitability() {
        try {
            const d = await fetchJSON(`/api/profitability?${filterQS()}`);

            upsert('profit', 'profitChart', {
                data: {
                    labels: d.labels.map((l) => truncate(l, 12)),
                    datasets: [
                        {
                            type: 'bar',
                            label: 'Sales',
                            data: d.sales,
                            backgroundColor: hexA(C.violet, 0.6),
                            borderColor: C.violet,
                            borderWidth: 1.4,
                            borderRadius: 7,
                            borderSkipped: false,
                            maxBarThickness: 40,
                            yAxisID: 'y',
                        },
                        {
                            type: 'bar',
                            label: 'Profit',
                            data: d.profit,
                            backgroundColor: hexA(C.green, 0.8),
                            borderColor: C.green,
                            borderWidth: 1.4,
                            borderRadius: 7,
                            borderSkipped: false,
                            maxBarThickness: 40,
                            yAxisID: 'y',
                        },
                        {
                            type: 'line',
                            label: 'Margin %',
                            data: d.margins,
                            borderColor: C.coral,
                            backgroundColor: C.coral,
                            borderWidth: 2.2,
                            tension: 0.3,
                            pointRadius: 3,
                            yAxisID: 'y1',
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, font: { size: 11 } } },
                        tooltip: {
                            callbacks: {
                                label: (c) => c.dataset.yAxisID === 'y1'
                                    ? ` Margin: ${c.parsed.y}%`
                                    : ` ${c.dataset.label}: ${fmtCurrency(c.parsed.y)}`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { color: C.axis, font: { size: 10.5 } },
                        },
                        y: {
                            beginAtZero: true,
                            position: 'left',
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                        y1: {
                            position: 'right',
                            grid: { display: false },
                            border: { display: false },
                            ticks: { callback: (v) => v + '%', color: C.coral },
                        },
                    },
                },
            });
        } catch (err) {
            showEmpty('profitChart', 'badge-dollar-sign', 'Profit column not present in this dataset.');
        }
    }

    /* ============================================================
       04 · SEASONALITY HEATMAP
       ============================================================ */
    async function loadHeatmap() {
        const wrap = document.getElementById('heatmap');
        if (!wrap) return;

        try {
            const d = await fetchJSON(`/api/heatmap?${filterQS()}`);
            const all = d.series.flatMap((s) => s.values);
            const max = Math.max(...all, 1);

            const header = `
                <div class="hm-row hm-header">
                    <span class="hm-label">Category</span>
                    ${d.months.map((m) => `<span class="hm-label">${m}</span>`).join('')}
                </div>`;

            const rows = d.series.map((s) => `
                <div class="hm-row">
                    <span class="hm-label" title="${s.category}">${s.category}</span>
                    ${s.values.map((v) => {
                        const intensity = v / max;
                        return `<div class="hm-cell" style="--i:${(intensity * 0.85 + 0.06).toFixed(3)}"
                                     title="${s.category}: ${fmtCurrency(v)}">
                                    ${intensity > 0.4 ? fmtCompact(v) : ''}
                                </div>`;
                    }).join('')}
                </div>`).join('');

            wrap.innerHTML = header + rows;
            wrap.parentElement?.classList.add('loaded');
        } catch (err) {
            wrap.innerHTML = '<p style="color:#7A8496;padding:20px">Heatmap unavailable.</p>';
            wrap.parentElement?.classList.add('loaded');
        }
    }

    /* ============================================================
       05 · MODEL METRICS + RESIDUALS
       ============================================================ */
    async function loadModel() {
        try {
            const m = await fetchJSON('/api/model/metrics');
            const box = document.getElementById('modelMetrics');
            const status = document.getElementById('modelStatus');

            if (box) {
                box.innerHTML = `
                    <div class="metric-cell">
                        <span class="metric-val">${fmtNumber(m.mae, 0)}</span>
                        <span class="metric-lbl">MAE</span>
                        <span class="metric-sub">mean absolute error</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-val">${m.mape != null ? m.mape + '%' : fmtCompact(m.mse)}</span>
                        <span class="metric-lbl">${m.mape != null ? 'MAPE' : 'MSE'}</span>
                        <span class="metric-sub">${m.mape != null ? 'avg % error' : 'mean squared error'}</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-val ${m.r2 >= 0 ? 'good' : ''}">${m.r2}</span>
                        <span class="metric-lbl">R² Score</span>
                        <span class="metric-sub">cross-validated</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-val">${m.train_r2}</span>
                        <span class="metric-lbl">Training R²</span>
                        <span class="metric-sub">fit on full data</span>
                    </div>`;
            }
            if (status) {
                status.textContent = `trained ${m.trained_at || ''}`.trim();
                status.className = 'chip chip-emerald';
            }

            loadResiduals();
        } catch (err) {
            const status = document.getElementById('modelStatus');
            if (status) {
                status.textContent = 'not trained';
                status.className = 'chip';
            }
            const box = document.getElementById('modelMetrics');
            if (box) {
                box.innerHTML = `
                    <div class="empty-mini" style="grid-column:1/-1">
                        <i data-lucide="brain"></i>
                        <p>No model trained yet — upload a dataset with ≥ 12 months of history.</p>
                    </div>`;
                window.refreshIcons();
            }
            showEmpty('residualChart', 'brain',
                'Train a model to see residual errors.');
        }
    }

    async function loadResiduals() {
        try {
            const d = await fetchJSON('/api/forecast/residuals');

            upsert('residuals', 'residualChart', {
                type: 'bar',
                data: {
                    labels: d.labels.map(shortMonth),
                    datasets: [{
                        label: 'Residual (actual − predicted)',
                        data: d.residuals,
                        backgroundColor: d.residuals.map((v) =>
                            v >= 0 ? hexA(C.green, 0.75) : hexA(C.red, 0.75)),
                        borderRadius: 5,
                        borderSkipped: false,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (c) => ' ' + fmtCurrency(c.parsed.y) } },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { color: '#E8EAEF' },
                            ticks: { maxTicksLimit: 10, maxRotation: 0, color: C.axis, font: { size: 10 } },
                        },
                        y: {
                            grid: { color: C.grid },
                            border: { display: false },
                            ticks: { callback: (v) => fmtCompact(v), color: C.axis },
                        },
                    },
                },
            });
        } catch (err) {
            console.error('Residuals unavailable:', err);
        }
    }

    /* ============================================================
       FILTERS
       ============================================================ */
    async function initFilters() {
        const regionSel = el('fRegion');
        if (!regionSel) return;            // page has no filter bar (forecasts/explorer)

        try {
            const f = await fetchJSON('/api/filters');
            const catSel = el('fCategory');
            const from = el('fFrom');
            const to = el('fTo');

            f.regions.forEach((r) => regionSel.add(new Option(r, r)));
            f.categories.forEach((c) => catSel?.add(new Option(c, c)));
            if (from && f.date_min) { from.min = f.date_min; from.max = f.date_max; }
            if (to && f.date_max) { to.min = f.date_min; to.max = f.date_max; }

            // Restore filters persisted from another page
            regionSel.value = state.filters.region || '';
            if (catSel) catSel.value = state.filters.category || '';
            if (from) from.value = state.filters.date_from || '';
            if (to) to.value = state.filters.date_to || '';
        } catch (err) {
            console.error('Filter init failed:', err);
        }

        el('btnApplyFilters')?.addEventListener('click', () => {
            state.filters = {
                region: el('fRegion')?.value || '',
                category: el('fCategory')?.value || '',
                date_from: el('fFrom')?.value || '',
                date_to: el('fTo')?.value || '',
            };
            saveFilters();                  // carry over to the other MPA pages
            state.page = 1;
            refreshAll();
            toast('Filters applied.', 'success');
        });

        el('btnClearFilters')?.addEventListener('click', () => {
            ['fRegion', 'fCategory', 'fFrom', 'fTo'].forEach((id) => {
                const node = el(id);
                if (node) node.value = '';
            });
            state.filters = { region: '', category: '', date_from: '', date_to: '' };
            saveFilters();
            state.page = 1;
            refreshAll();
            toast('Filters cleared.', 'info');
        });
    }

    /* ============================================================
       EXPLORER SEARCH (server-side, debounced)
       ============================================================ */
    function initExplorerSearch() {
        const input = el('searchInput');
        if (!input) return;

        let timer = null;
        input.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                state.search = input.value.trim();
                state.page = 1;
                loadTable();
            }, 300);
        });
    }

    /* ============================================================
       FORECAST SIMULATOR
       ============================================================ */
    function initForecast() {
        const form = document.getElementById('forecastForm');
        const result = document.getElementById('forecastResult');
        const hideBtn = document.getElementById('btnHideResult');

        const yearInput = document.getElementById('fcYear');
        if (yearInput) yearInput.value = new Date().getFullYear() + 1;

        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button[type="submit"]');
            btn.classList.add('loading');
            btn.disabled = true;

            try {
                const data = await fetchJSON('/api/forecast', {
                    method: 'POST',
                    body: JSON.stringify({
                        month: parseInt(document.getElementById('fcMonth').value, 10),
                        year: parseInt(yearInput.value, 10),
                    }),
                });

                document.getElementById('resultValue').textContent =
                    fmtCurrency(data.predicted_sales);
                document.getElementById('resultPeriod').textContent = data.month_name;
                result.hidden = false;
                result.style.animation = 'none';
                void result.offsetHeight;
                result.style.animation = '';
            } catch (err) {
                toast(err.message, 'danger');
            } finally {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        });

        hideBtn?.addEventListener('click', () => { result.hidden = true; });
    }

    function initTimeline() {
        const btn = document.getElementById('btnLoadTimeline');
        const wrap = document.getElementById('timeline');

        btn?.addEventListener('click', async () => {
            btn.classList.add('loading');
            btn.disabled = true;

            try {
                const now = new Date();
                const d = await fetchJSON('/api/forecast/multiple', {
                    method: 'POST',
                    body: JSON.stringify({
                        months: 6,
                        start_month: now.getMonth() + 1,
                        start_year: now.getFullYear(),
                    }),
                });

                const max = Math.max(...d.forecasts.map((f) => f.predicted_sales), 1);

                wrap.innerHTML = d.forecasts.map((f, i) => `
                    <div class="tl-item" style="animation-delay:${i * 70}ms">
                        <span class="tl-month">${f.month_name}</span>
                        <div class="tl-bar-wrap">
                            <div class="tl-bar"
                                 style="width:${Math.max(4, (f.predicted_sales / max) * 100)}%;
                                        animation-delay:${i * 70 + 120}ms"></div>
                        </div>
                        <span class="tl-value">${fmtCurrency(f.predicted_sales)}</span>
                    </div>`).join('');
            } catch (err) {
                toast(err.message, 'danger');
            } finally {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        });
    }

    /* ============================================================
       DATA EXPLORER
       ============================================================ */
    async function loadTable() {
        try {
            const searchQS = state.search
                ? `&search=${encodeURIComponent(state.search)}` : '';
            const d = await fetchJSON(
                `/api/table?${filterQS()}&page=${state.page}` +
                `&per_page=${state.perPage}${searchQS}`
            );

            const cols = d.rows.length ? Object.keys(d.rows[0]) : [];
            const head = document.getElementById('tableHead');
            const body = document.getElementById('tableBody');
            if (head) head.innerHTML = cols.map((c) => `<th>${c}</th>`).join('');
            if (body) {
                body.innerHTML = d.rows
                    .map((row) => `<tr>${cols.map((c) => `<td>${row[c] ?? ''}</td>`).join('')}</tr>`)
                    .join('');
            }

            const count = document.getElementById('explorerCount');
            if (count) count.textContent = `${fmtNumber(d.total)} rows`;

            // Active search chip
            const chip = document.getElementById('searchChip');
            if (chip) {
                if (state.search) {
                    chip.hidden = false;
                    chip.textContent = `search: “${state.search}”`;
                    chip.className = 'chip chip-coral';
                } else {
                    chip.hidden = true;
                }
            }

            renderPager(d.page, d.pages);
        } catch (err) {
            console.error('Table load failed:', err);
        }
    }

    function renderPager(page, pages) {
        const pager = document.getElementById('pager');
        if (!pager) return;
        pager.innerHTML = `
            <button ${page <= 1 ? 'disabled' : ''} data-p="${page - 1}">‹ Prev</button>
            <span class="page-info">Page ${page} of ${pages}</span>
            <button ${page >= pages ? 'disabled' : ''} data-p="${page + 1}">Next ›</button>`;

        pager.querySelectorAll('button[data-p]').forEach((b) => {
            b.addEventListener('click', () => {
                state.page = parseInt(b.dataset.p, 10);
                loadTable();
            });
        });
    }

    /* ============================================================
       ORCHESTRATION — only loads modules that exist on this page
       ============================================================ */
    function refreshAll() {
        if (el('kpiGrid')) loadKPIs();
        if (el('insightGrid')) loadInsights();
        if (el('trendChart')) loadTrend();
        if (el('cumulativeChart')) loadCumulative();
        if (el('categoryChart')) loadCategory();
        if (el('regionChart')) loadRegion();
        if (el('paretoChart')) loadPareto();
        if (el('compareChart')) loadCompare();
        if (el('growthChart')) loadGrowth();
        if (el('distChart')) loadDistribution();
        if (el('scatterChart')) loadScatter();
        if (el('profitChart')) loadProfitability();
        if (el('heatmap')) loadHeatmap();
        if (el('tableHead')) loadTable();
    }

    /* ---------- Boot: same script, six different pages ---------- */
    document.addEventListener('DOMContentLoaded', () => {
        applyChartDefaults();

        initFilters();            // no-ops when the page has no filter bar
        refreshAll();             // loads only the modules present on this page
        if (el('modelMetrics')) loadModel();

        initForecast();           // guards on #forecastForm
        initTimeline();           // guards on #btnLoadTimeline
        initExplorerSearch();     // guards on #searchInput

        el('btnRefresh')?.addEventListener('click', () => {
            refreshAll();
            if (el('modelMetrics')) loadModel();
            toast('Page reloaded.', 'info');
        });
    });
})();
