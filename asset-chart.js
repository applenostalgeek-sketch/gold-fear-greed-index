/*
 * asset-chart.js — Single-series chart + UI for asset detail pages
 *
 * Requires: shared.js loaded first
 * Requires: window.ASSET_CONFIG set before this script:
 *   {
 *     color: '#FFD700',
 *     name: 'Gold',
 *     dataUrl: 'data/gold-fear-greed.json',
 *     phrases: { extremeFear, fear, neutral, greed, extremeGreed }
 *   }
 */

(function () {
    const CFG = window.ASSET_CONFIG;
    if (!CFG) { console.error('ASSET_CONFIG not set'); return; }

    let assetData = null;
    let chartHistory = [];
    let currentPeriod = 30;

    // ==================== Data Load ====================

    async function loadData() {
        try {
            const response = await fetch(CFG.dataUrl);
            assetData = await response.json();
            updateUI();
            updateHistoryChart(30);
        } catch (error) {
            console.error('Error:', error);
        }
    }

    // ==================== UI Update ====================

    function updateUI() {
        if (!assetData) return;

        const score = assetData.score;
        const position = score;

        // Score with trend arrow
        const scoreEl = document.getElementById('score');
        let arrow = '';
        if (assetData.history && assetData.history.length >= 2) {
            const sorted = [...assetData.history].sort((a, b) => new Date(b.date) - new Date(a.date));
            const diff = sorted[0].score - sorted[1].score;
            if (diff > 2) arrow = '↑';
            else if (diff < -2) arrow = '↓';
            else arrow = '→';
        }
        scoreEl.innerHTML = Math.round(score) + (arrow ? '<span class="hero-trend-arrow">' + arrow + '</span>' : '');

        // Label and color
        let label, color;
        if (position < 25) { label = "EXTREME FEAR"; color = "#ef4444"; }
        else if (position < 45) { label = "FEAR"; color = "#f59e0b"; }
        else if (position < 55) { label = "NEUTRAL"; color = "#ffffff"; }
        else if (position < 75) { label = "GREED"; color = "#22c55e"; }
        else { label = "EXTREME GREED"; color = "#06b6d4"; }

        // Bar
        const barFill = document.getElementById('barFill');
        barFill.style.width = position + '%';
        barFill.style.backgroundColor = color;

        document.getElementById('label').textContent = label;
        scoreEl.style.color = color;

        // Timestamp
        if (assetData.timestamp) {
            const date = new Date(assetData.timestamp);
            const timeText = 'Updated: ' + date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + ', ' + date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
            document.getElementById('updated').textContent = timeText;
        }

        // Insight box styling
        const insightBox = document.querySelector('.insight-box');
        insightBox.style.borderLeftColor = color;
        const rc = parseInt(color.slice(1,3), 16);
        const gc = parseInt(color.slice(3,5), 16);
        const bc = parseInt(color.slice(5,7), 16);
        insightBox.style.backgroundColor = `rgba(${rc}, ${gc}, ${bc}, 0.07)`;

        // Insight text
        if (assetData.components) {
            let phrase1 = '';
            if (score < 25) phrase1 = CFG.phrases.extremeFear;
            else if (score < 45) phrase1 = CFG.phrases.fear;
            else if (score < 55) phrase1 = CFG.phrases.neutral;
            else if (score < 75) phrase1 = CFG.phrases.greed;
            else phrase1 = CFG.phrases.extremeGreed;

            const factPhrase = buildFactPhrase(assetData, score);
            document.getElementById('insight').textContent = phrase1 + ' ' + factPhrase;
        }

        // Components
        if (assetData.components) {
            const grid = document.getElementById('componentsGrid');
            grid.innerHTML = '';
            Object.entries(assetData.components).forEach(([name, data]) => {
                const card = document.createElement('div');
                card.className = 'component-card';
                card.innerHTML = '<div class="component-name">' + escapeHtml(name) + '</div>'
                    + '<div class="component-score" style="color: ' + getColor(data.score) + '">' + Math.round(data.score) + '</div>'
                    + '<div class="component-detail">' + escapeHtml(data.detail) + '</div>';
                grid.appendChild(card);
            });
        }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ==================== Fact Phrase ====================

    function buildFactPhrase(data, score) {
        const history = data.history || [];
        if (history.length < 2) return '';

        const getZone = s => s <= 25 ? 'EF' : s <= 45 ? 'F' : s <= 55 ? 'N' : s <= 75 ? 'G' : 'EG';
        const weeklyDiff = history.length >= 7 ? Math.round(score - history[6].score) : 0;

        // 30-day extremes
        let is30dHigh = false, is30dLow = false;
        if (history.length >= 30) {
            const scores30 = history.slice(0, 30).map(h => h.score);
            if (score >= Math.max(...scores30) - 1) is30dHigh = true;
            if (score <= Math.min(...scores30) + 1) is30dLow = true;
        }

        // Streak
        const dir = history[0].score > history[1].score ? 1 : -1;
        let streak = 1;
        for (let i = 1; i < history.length - 1; i++) {
            if (dir > 0 && history[i].score > history[i+1].score) streak++;
            else if (dir < 0 && history[i].score < history[i+1].score) streak++;
            else break;
        }
        streak *= dir;

        // Stability
        let daysNear = 1;
        for (let i = 1; i < Math.min(history.length, 14); i++) {
            if (Math.abs(history[i].score - score) <= 5) daysNear++;
            else break;
        }

        // Priority selection
        if (is30dLow) return 'Lowest score in 30 days.';
        if (is30dHigh) return 'Highest score in 30 days.';
        if (Math.abs(weeklyDiff) > 10) return (weeklyDiff > 0 ? 'Up' : 'Down') + ' ' + Math.abs(weeklyDiff) + ' pts this week.';
        if (Math.abs(streak) >= 5) return (streak > 0 ? 'Rising' : 'Falling') + ' ' + Math.abs(streak) + ' days straight.';
        if (getZone(history[0].score) !== getZone(history[1].score)) return 'Just entered ' + data.label + '.';
        if (Math.abs(weeklyDiff) > 5) return (weeklyDiff > 0 ? 'Up' : 'Down') + ' ' + Math.abs(weeklyDiff) + ' pts this week.';
        if (daysNear >= 3) return 'Holding near ' + Math.round(score) + ' for ' + daysNear + ' days.';
        return 'No major move recently.';
    }

    // ==================== Chart ====================

    function drawChart() {
        const canvas = document.getElementById('historyChart');
        const { ctx, w, h, pad, plotW, plotH } = getChartLayout(canvas);

        ctx.clearRect(0, 0, w, h);

        // Zone bands
        zones.forEach(zone => {
            const yTop = scoreToY(zone.to, pad, plotH);
            const yBot = scoreToY(zone.from, pad, plotH);
            ctx.fillStyle = zone.color;
            ctx.fillRect(pad.left, yTop, plotW, yBot - yTop);
        });

        // Zone labels
        zoneLabels.forEach(zl => {
            const y = scoreToY(zl.score, pad, plotH) + 4;
            ctx.fillStyle = zl.color;
            ctx.font = '10px -apple-system, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(zl.text, pad.left + plotW - 6, y);
        });

        // Separators
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
        ctx.lineWidth = 1;
        [25, 45, 55, 75].forEach(s => {
            const y = scoreToY(s, pad, plotH);
            ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + plotW, y); ctx.stroke();
        });

        // 50 line
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.setLineDash([4, 4]);
        const y50 = scoreToY(50, pad, plotH);
        ctx.beginPath(); ctx.moveTo(pad.left, y50); ctx.lineTo(pad.left + plotW, y50); ctx.stroke();
        ctx.setLineDash([]);

        // Data line
        if (chartHistory.length >= 2) {
            ctx.strokeStyle = CFG.color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            chartHistory.forEach((p, i) => {
                const x = indexToX(i, chartHistory.length, pad, plotW);
                const y = scoreToY(p.score, pad, plotH);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();

            // End dot
            const last = chartHistory[chartHistory.length - 1];
            const lx = indexToX(chartHistory.length - 1, chartHistory.length, pad, plotW);
            const ly = scoreToY(last.score, pad, plotH);
            ctx.beginPath();
            ctx.arc(lx, ly, 4, 0, Math.PI * 2);
            ctx.fillStyle = CFG.color;
            ctx.fill();
        }

        // Date labels
        if (chartHistory.length > 0) {
            const total = chartHistory.length;
            const numLabels = Math.min(total, w < 500 ? 4 : 6);
            ctx.fillStyle = '#555';
            ctx.font = '10px -apple-system, sans-serif';
            for (let i = 0; i < numLabels; i++) {
                const idx = i === numLabels - 1 ? total - 1 : Math.round(i * (total - 1) / (numLabels - 1));
                const x = indexToX(idx, total, pad, plotW);
                const date = new Date(chartHistory[idx].date);
                const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                if (i === 0) ctx.textAlign = 'left';
                else if (i === numLabels - 1) ctx.textAlign = 'right';
                else ctx.textAlign = 'center';
                ctx.fillText(label, x, h - 8);
            }
        }
    }

    // ==================== Tooltip ====================

    function handleChartHover(e) {
        const canvas = document.getElementById('historyChart');
        const tooltip = document.getElementById('chartTooltip');
        const rect = canvas.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const x = clientX - rect.left;
        const box = canvas.parentElement;
        const pad = { left: 30, right: 30 };
        const plotW = box.clientWidth - pad.left - pad.right;

        if (!chartHistory || chartHistory.length < 2) return;

        const ratio = Math.max(0, Math.min(1, (x - pad.left) / plotW));
        const idx = Math.round(ratio * (chartHistory.length - 1));
        const point = chartHistory[idx];
        if (!point) return;

        const date = new Date(point.date);
        document.getElementById('tooltipDate').textContent = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        document.getElementById('tooltipRows').innerHTML = '<div class="chart-tooltip-row">'
            + '<span class="chart-tooltip-name" style="color:' + CFG.color + '">' + CFG.name + '</span>'
            + '<span class="chart-tooltip-val" style="color:' + CFG.color + '">' + Math.round(point.score) + '</span></div>';

        const tooltipLeft = x > rect.width * 0.6 ? 20 : rect.width - 180;
        tooltip.style.left = tooltipLeft + 'px';
        tooltip.style.display = 'block';

        // Crosshair
        drawChart();
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        ctx.save();
        ctx.scale(1/dpr, 1/dpr);
        const lineX = (pad.left + ratio * plotW) * dpr;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(lineX, 16 * dpr);
        ctx.lineTo(lineX, (box.clientHeight - 28) * dpr);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
    }

    // ==================== History ====================

    function updateHistoryChart(days) {
        if (!assetData || !assetData.history) return;
        chartHistory = [...assetData.history].sort((a, b) => new Date(a.date) - new Date(b.date)).slice(-days);
        drawChart();
    }

    // ==================== Event Listeners ====================

    // Period buttons
    document.querySelectorAll('.period-btn').forEach(button => {
        button.addEventListener('click', () => {
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            button.classList.add('active');
            currentPeriod = parseInt(button.dataset.period);
            updateHistoryChart(currentPeriod);
        });
    });

    // Tooltip events
    const chartCanvas = document.getElementById('historyChart');
    if (chartCanvas) {
        chartCanvas.addEventListener('mousemove', handleChartHover);
        chartCanvas.addEventListener('mouseleave', () => { hideTooltip(); drawChart(); });
        chartCanvas.addEventListener('touchmove', (e) => { e.preventDefault(); handleChartHover(e); }, { passive: false });
        chartCanvas.addEventListener('touchend', () => { hideTooltip(); drawChart(); });
    }

    // Resize
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => drawChart(), 200);
    });

    // ==================== Init ====================

    loadData();
    updateLogoDots();
})();
