/* shared.js — Utilities used across multiple pages */

function getColor(score) {
    if (score <= 25) return '#ef4444';
    if (score <= 45) return '#f59e0b';
    if (score <= 55) return '#ffffff';
    if (score <= 75) return '#22c55e';
    return '#06b6d4';
}

function getChartLayout(canvas) {
    const box = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = box.clientWidth * dpr;
    canvas.height = box.clientHeight * dpr;
    canvas.style.width = box.clientWidth + 'px';
    canvas.style.height = box.clientHeight + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const w = box.clientWidth;
    const h = box.clientHeight;
    const pad = { top: 16, bottom: 32, left: 30, right: 30 };
    return { ctx, w, h, pad, plotW: w - pad.left - pad.right, plotH: h - pad.top - pad.bottom };
}

function scoreToY(score, pad, plotH) {
    return pad.top + plotH - (score / 100) * plotH;
}

function indexToX(i, total, pad, plotW) {
    return pad.left + (total > 1 ? (i / (total - 1)) * plotW : plotW / 2);
}

const zones = [
    { from: 0,  to: 25,  color: 'rgba(239, 68, 68, 0.07)' },
    { from: 25, to: 45,  color: 'rgba(245, 158, 11, 0.05)' },
    { from: 45, to: 55,  color: 'rgba(255, 255, 255, 0.02)' },
    { from: 55, to: 75,  color: 'rgba(34, 197, 94, 0.05)' },
    { from: 75, to: 100, color: 'rgba(6, 182, 212, 0.07)' }
];

const zoneLabels = [
    { score: 12.5, text: 'Extreme Fear', color: 'rgba(239, 68, 68, 0.35)' },
    { score: 35,   text: 'Fear',         color: 'rgba(245, 158, 11, 0.3)' },
    { score: 50,   text: 'Neutral',      color: 'rgba(255, 255, 255, 0.15)' },
    { score: 65,   text: 'Greed',        color: 'rgba(34, 197, 94, 0.3)' },
    { score: 87.5, text: 'Extreme Greed', color: 'rgba(6, 182, 212, 0.35)' }
];

function hideTooltip() {
    const el = document.getElementById('chartTooltip');
    if (el) el.style.display = 'none';
}

/* Mobile menu */
(function initMobileMenu() {
    const toggle = document.querySelector('.mobile-menu-toggle');
    const links = document.querySelector('.nav-links');
    const overlay = document.querySelector('.mobile-menu-overlay');
    if (!toggle || !links) return;

    function toggleMenu() {
        toggle.classList.toggle('active');
        links.classList.toggle('active');
        if (overlay) overlay.classList.toggle('active');
        document.body.style.overflow = links.classList.contains('active') ? 'hidden' : '';
    }

    toggle.addEventListener('click', toggleMenu);
    if (overlay) overlay.addEventListener('click', toggleMenu);

    links.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 768) toggleMenu();
        });
    });
})();

/* Logo dots — shows market sentiment color */
async function updateLogoDots() {
    try {
        const [bondsRes, goldRes, stocksRes, cryptoRes] = await Promise.all([
            fetch('data/bonds-fear-greed.json'),
            fetch('data/gold-fear-greed.json'),
            fetch('data/stocks-fear-greed.json'),
            fetch('data/crypto-fear-greed.json')
        ]);
        const bonds = await bondsRes.json();
        const gold = await goldRes.json();
        const stocks = await stocksRes.json();
        const crypto = await cryptoRes.json();

        const riskOn = (stocks.score + crypto.score) / 2;
        const riskOff = (bonds.score + gold.score) / 2;
        const position = ((riskOn - riskOff + 100) / 200) * 100;

        const logoDots = document.querySelector('.logo-dots');
        if (logoDots) logoDots.style.color = getColor(position);
    } catch (error) {
        console.error('Error updating logo dots:', error);
    }
}
