/**
 * Nexus Analytics — Core UI interactions
 * Mobile navigation, dropdowns, flash messages, toast, formatters.
 */

(function () {
    'use strict';

    /* ---------- Mobile navigation drawer ---------- */
    const navToggle = document.getElementById('navToggle');
    const mobileNav = document.getElementById('mobileNav');

    navToggle?.addEventListener('click', (e) => {
        e.stopPropagation();
        mobileNav?.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
        if (mobileNav?.classList.contains('open') &&
            !mobileNav.contains(e.target) && e.target !== navToggle) {
            mobileNav.classList.remove('open');
        }
    });

    /* ---------- Export dropdown ---------- */
    const exportToggle = document.getElementById('exportToggle');
    const exportMenu = document.getElementById('exportMenu');

    exportToggle?.addEventListener('click', (e) => {
        e.stopPropagation();
        exportMenu?.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
        if (exportMenu && !exportMenu.contains(e.target) && e.target !== exportToggle) {
            exportMenu.classList.remove('open');
        }
    });

    /* ---------- Flash auto-dismiss ---------- */
    document.querySelectorAll('[data-flash]').forEach((el, i) => {
        setTimeout(() => {
            el.style.transition = 'opacity .35s, transform .35s';
            el.style.opacity = '0';
            el.style.transform = 'translateY(-8px)';
            setTimeout(() => el.remove(), 380);
        }, 6000 + i * 400);
    });

    /* ---------- Re-init dynamically injected icons ---------- */
    window.refreshIcons = function () {
        if (window.lucide) lucide.createIcons();
    };

    /* ---------- Toast helper ---------- */
    window.toast = function (message, type = 'info') {
        const stack = document.querySelector('.flash-stack');
        const icons = {
            success: 'check-circle',
            danger: 'alert-triangle',
            warning: 'alert-triangle',
            info: 'info',
        };
        const el = document.createElement('div');
        el.className = `flash flash-${type}`;
        el.setAttribute('data-flash', '');
        el.innerHTML = `
            <i data-lucide="${icons[type] || 'info'}"></i>
            <span>${message}</span>
            <button class="flash-close"><i data-lucide="x"></i></button>`;
        el.querySelector('.flash-close').onclick = () => el.remove();

        if (stack) stack.appendChild(el);
        else document.querySelector('.content')?.prepend(el);

        refreshIcons();
        setTimeout(() => el.remove(), 5500);
    };

    /* ---------- Formatters ---------- */
    window.fmtCurrency = (v, digits = 0) =>
        new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(v);

    window.fmtNumber = (v, digits = 0) =>
        new Intl.NumberFormat('en-US', {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(v);

    window.fmtCompact = (v) => {
        if (Math.abs(v) >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
        if (Math.abs(v) >= 1e3) return '$' + (v / 1e3).toFixed(1) + 'K';
        return '$' + Number(v).toFixed(0);
    };

    /** fetch JSON with error propagation */
    window.fetchJSON = async (url, opts = {}) => {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
            ...opts,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        return data;
    };
})();
