/*
 * asset-chart.js — Dual-axis chart + UI for asset detail pages
 *
 * Requires: shared.js loaded first
 * Requires: window.ASSET_CONFIG set before this script:
 *   {
 *     color: '#FFD700',
 *     name: 'Gold',
 *     dataUrl: 'data/gold-fear-greed.json',
 *     priceLabel: 'GLD',
 *     priceColor: '#FFD700',
 *     phrases: { extremeFear, fear, neutral, greed, extremeGreed }
 *   }
 */

(function () {
    const CFG = window.ASSET_CONFIG;
    if (!CFG) { console.error('ASSET_CONFIG not set'); return; }

    let assetData = null;
    let chartHistory = [];
    let currentPeriod = 30;

    // ==================== Circle Wave Animation ====================

    let circleWaveOffset = 0;
    let circleTargetFillY = 200;
    let circleCurrentFillY = 200;

    function buildWave(baseY, amp, freq, offset) {
        let d = `M 0 ${baseY}`;
        for (let x = 0; x <= 200; x += 5) {
            d += ` L ${x} ${baseY + Math.sin((x / freq) + offset) * amp}`;
        }
        return d + ' L 200 200 L 0 200 Z';
    }

    function animateCircle() {
        circleWaveOffset += 0.03;
        circleCurrentFillY += (circleTargetFillY - circleCurrentFillY) * 0.04;
        const y = circleCurrentFillY;
        const t = circleWaveOffset;

        const wave = document.getElementById('wave');
        if (wave) wave.setAttribute('d', buildWave(y, 3, 30, t));
        const mid = document.getElementById('wave-mid');
        if (mid) mid.setAttribute('d', buildWave(y + 6, 4, 45, t * 0.7 + 2));
        const deep = document.getElementById('wave-deep');
        if (deep) deep.setAttribute('d', buildWave(y + 14, 5, 60, t * 0.4 + 4.5));

        requestAnimationFrame(animateCircle);
    }
    animateCircle();

    // ==================== Toggle Helpers ====================

    function isIndexVisible() {
        const btn = document.querySelector('.chart-toggle-btn[data-series="index"]');
        return !btn || btn.classList.contains('active');
    }

    function isPriceVisible() {
        const btn = document.querySelector('.chart-toggle-btn[data-series="price"]');
        return !btn || btn.classList.contains('active');
    }

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

        // Trend arrow
        const scoreEl = document.getElementById('score');
        let arrow = '';
        if (assetData.history && assetData.history.length >= 2) {
            const sorted = [...assetData.history].sort((a, b) => new Date(b.date) - new Date(a.date));
            const diff = sorted[0].score - sorted[1].score;
            if (diff > 2) arrow = '↑';
            else if (diff < -2) arrow = '↓';
            else arrow = '→';
        }

        // Score (SVG text)
        scoreEl.textContent = Math.round(score);

        // Trend arrow (SVG, position dynamique)
        const arrowEl = document.getElementById('trendArrow');
        if (arrowEl && arrow) {
            arrowEl.textContent = arrow;
            const scoreWidth = scoreEl.getComputedTextLength ? scoreEl.getComputedTextLength() : 60;
            arrowEl.setAttribute('x', 100 + scoreWidth / 2 + 6);
        }

        // Label and color (based on rounded score to match display)
        const rounded = Math.round(score);
        let label, color, glow;
        if (rounded <= 25) { label = "EXTREME FEAR"; color = "#ef4444"; glow = "glow-red"; }
        else if (rounded <= 45) { label = "FEAR"; color = "#f59e0b"; glow = "glow-orange"; }
        else if (rounded <= 55) { label = "NEUTRAL"; color = "#ffffff"; glow = "glow-white"; }
        else if (rounded <= 75) { label = "GREED"; color = "#22c55e"; glow = "glow-green"; }
        else { label = "EXTREME GREED"; color = "#06b6d4"; glow = "glow-cyan"; }

        // Circle fill
        const CIRCLE_BOTTOM = 190, CIRCLE_RANGE = 180;
        circleTargetFillY = CIRCLE_BOTTOM - (position / 100) * CIRCLE_RANGE;
        document.getElementById('grad-stop-1').setAttribute('stop-color', color);
        document.getElementById('grad-stop-2').setAttribute('stop-color', color);
        document.querySelector('.circle-outline').style.stroke = color;
        document.querySelector('.circle-outline').style.strokeOpacity = 0.25;
        document.getElementById('circle-container').className = 'circle-container ' + glow;
        scoreEl.style.fill = '#fff';

        document.getElementById('label').textContent = label;

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
            if (rounded <= 25) phrase1 = CFG.phrases.extremeFear;
            else if (rounded <= 45) phrase1 = CFG.phrases.fear;
            else if (rounded <= 55) phrase1 = CFG.phrases.neutral;
            else if (rounded <= 75) phrase1 = CFG.phrases.greed;
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

        // Dynamic right padding based on whether price axis is shown
        const showPrice = isPriceVisible() && chartHistory.some(p => p.price != null);
        const pad = { top: 16, bottom: 32, left: 30, right: showPrice ? 56 : 30 };
        const plotW = w - pad.left - pad.right;
        const plotH = h - pad.top - pad.bottom;

        ctx.clearRect(0, 0, w, h);

        // Price data setup
        let pMin, pMax, pRange, pPad;
        if (showPrice) {
            const prices = chartHistory.filter(p => p.price != null).map(p => p.price);
            pMin = Math.min(...prices);
            pMax = Math.max(...prices);
            pRange = pMax - pMin || 1;
            pPad = pRange * 0.08;
        }

        function priceToY(p) {
            return pad.top + plotH - ((p - pMin + pPad) / (pRange + pPad * 2)) * plotH;
        }

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

        // Price line (behind score line)
        if (showPrice && chartHistory.length >= 2) {
            ctx.strokeStyle = (CFG.priceColor || CFG.color) + '88';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            let started = false;
            chartHistory.forEach((p, i) => {
                if (p.price == null) return;
                const x = indexToX(i, chartHistory.length, pad, plotW);
                const y = priceToY(p.price);
                if (!started) { ctx.moveTo(x, y); started = true; }
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }

        // Score line (on top)
        if (isIndexVisible() && chartHistory.length >= 2) {
            ctx.strokeStyle = '#ffffff';
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
            ctx.fillStyle = '#ffffff';
            ctx.fill();
        }

        // Price end dot
        if (showPrice && chartHistory.length >= 2) {
            const lastWithPrice = [...chartHistory].reverse().find(p => p.price != null);
            if (lastWithPrice) {
                const idx = chartHistory.indexOf(lastWithPrice);
                const px = indexToX(idx, chartHistory.length, pad, plotW);
                const py = priceToY(lastWithPrice.price);
                ctx.beginPath();
                ctx.arc(px, py, 3, 0, Math.PI * 2);
                ctx.fillStyle = CFG.priceColor || CFG.color;
                ctx.fill();
            }
        }

        // Right axis — price labels
        if (showPrice) {
            ctx.textAlign = 'left';
            ctx.font = '10px -apple-system, sans-serif';
            ctx.fillStyle = (CFG.priceColor || CFG.color) + '88';
            const priceSteps = 5;
            for (let i = 0; i <= priceSteps; i++) {
                const p = pMin - pPad + (i / priceSteps) * (pRange + pPad * 2);
                const y = pad.top + plotH - (i / priceSteps) * plotH;
                let label;
                if (p >= 1000) label = '$' + Math.round(p).toLocaleString();
                else if (p < 10) label = '$' + p.toFixed(2);
                else label = '$' + p.toFixed(0);
                ctx.fillText(label, pad.left + plotW + 6, y + 3);
            }
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
        const showPrice = isPriceVisible() && chartHistory.some(p => p.price != null);
        const pad = { left: 30, right: showPrice ? 56 : 30 };
        const plotW = box.clientWidth - pad.left - pad.right;

        if (!chartHistory || chartHistory.length < 2) return;

        const ratio = Math.max(0, Math.min(1, (x - pad.left) / plotW));
        const idx = Math.round(ratio * (chartHistory.length - 1));
        const point = chartHistory[idx];
        if (!point) return;

        const date = new Date(point.date);
        document.getElementById('tooltipDate').textContent = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        let rows = '';
        if (isIndexVisible()) {
            rows += '<div class="chart-tooltip-row">'
                + '<span class="chart-tooltip-name" style="color:#fff">' + CFG.name + ' Index</span>'
                + '<span class="chart-tooltip-val" style="color:#fff">' + Math.round(point.score) + '</span></div>';
        }
        if (isPriceVisible() && point.price != null) {
            const pc = CFG.priceColor || CFG.color;
            let priceStr;
            if (point.price >= 1000) priceStr = '$' + Math.round(point.price).toLocaleString();
            else priceStr = '$' + point.price.toFixed(2);
            rows += '<div class="chart-tooltip-row">'
                + '<span class="chart-tooltip-name" style="color:' + pc + '">' + (CFG.priceLabel || 'Price') + '</span>'
                + '<span class="chart-tooltip-val" style="color:' + pc + '">' + priceStr + '</span></div>';
        }
        document.getElementById('tooltipRows').innerHTML = rows;

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

    // Toggle buttons
    document.querySelectorAll('.chart-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.classList.toggle('active');
            drawChart();
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
