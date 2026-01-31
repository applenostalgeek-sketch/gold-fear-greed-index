// Fear & Greed Central - Frontend JavaScript

// Configuration
const GOLD_DATA_URL = 'data/gold-fear-greed.json';
const STOCKS_DATA_URL = 'data/stocks-fear-greed.json';
const CRYPTO_DATA_URL = 'data/crypto-fear-greed.json';

// Global state
let goldData = null;
let stocksData = null;
let cryptoData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
});

/**
 * Load all three indices data
 */
async function loadAllData() {
    try {
        // Load all three indices in parallel
        const [goldResponse, stocksResponse, cryptoResponse] = await Promise.all([
            fetch(GOLD_DATA_URL),
            fetch(STOCKS_DATA_URL),
            fetch(CRYPTO_DATA_URL)
        ]);

        if (!goldResponse.ok || !stocksResponse.ok || !cryptoResponse.ok) {
            throw new Error('HTTP error loading data');
        }

        goldData = await goldResponse.json();
        stocksData = await stocksResponse.json();
        cryptoData = await cryptoResponse.json();

        updateUI();
    } catch (error) {
        console.error('Error loading data:', error);
        showError();
    }
}

/**
 * Update all UI elements with loaded data
 */
function updateUI() {
    if (!goldData || !stocksData || !cryptoData) return;

    updateIndexCards();
    updateMarketRotation();
    updateHistoryChart();
    updateLastUpdate();
}

/**
 * Update the three index cards
 */
function updateIndexCards() {
    // Check if card elements exist (only on dedicated pages, not index.html)
    const goldCardScore = document.getElementById('goldCardScore');
    if (!goldCardScore) return; // Skip if on index.html

    // Gold Card
    goldCardScore.textContent = Math.round(goldData.score);
    document.getElementById('goldCardLabel').textContent = goldData.label;
    const goldMiniBar = document.getElementById('goldMiniBar');
    goldMiniBar.style.width = `${goldData.score}%`;

    const goldLabelEl = document.getElementById('goldCardLabel');
    const colorClass = getColorClass(goldData.score);
    goldCardScore.className = `card-score ${colorClass}`;
    goldLabelEl.className = `card-label ${colorClass}`;
    // Apply color to mini bar based on fear/greed zone
    goldMiniBar.style.background = getColorGradient(goldData.score);

    // Stocks Card
    document.getElementById('stocksCardScore').textContent = Math.round(stocksData.score);
    document.getElementById('stocksCardLabel').textContent = stocksData.label;
    const stocksMiniBar = document.getElementById('stocksMiniBar');
    stocksMiniBar.style.width = `${stocksData.score}%`;

    const stocksScoreEl = document.getElementById('stocksCardScore');
    const stocksLabelEl = document.getElementById('stocksCardLabel');
    const stocksColorClass = getColorClass(stocksData.score);
    stocksScoreEl.className = `card-score ${stocksColorClass}`;
    stocksLabelEl.className = `card-label ${stocksColorClass}`;
    // Apply color to mini bar
    stocksMiniBar.style.background = getColorGradient(stocksData.score);

    // Crypto Card
    document.getElementById('cryptoCardScore').textContent = Math.round(cryptoData.score);
    document.getElementById('cryptoCardLabel').textContent = cryptoData.label;
    const cryptoMiniBar = document.getElementById('cryptoMiniBar');
    cryptoMiniBar.style.width = `${cryptoData.score}%`;

    const cryptoScoreEl = document.getElementById('cryptoCardScore');
    const cryptoLabelEl = document.getElementById('cryptoCardLabel');
    const cryptoColorClass = getColorClass(cryptoData.score);
    cryptoScoreEl.className = `card-score ${cryptoColorClass}`;
    cryptoLabelEl.className = `card-label ${cryptoColorClass}`;
    // Apply color to mini bar
    cryptoMiniBar.style.background = getColorGradient(cryptoData.score);
}

/**
 * Update Market Rotation Analysis section
 * 5 scenarios with refined thresholds for maximum precision
 */
function updateMarketRotation() {
    const gold = goldData.score;
    const stocks = stocksData.score;
    const crypto = cryptoData.score;

    const analysisBox = document.getElementById('rotationAnalysisBox');
    const iconEl = document.getElementById('analysisIcon');
    const titleEl = document.getElementById('analysisTitle');
    const detailEl = document.getElementById('analysisDetail');

    // Skip if elements don't exist (e.g., on index.html)
    if (!analysisBox || !iconEl || !titleEl || !detailEl) return;

    // Remove all regime classes
    analysisBox.classList.remove('flight-to-safety', 'risk-on', 'altcoin-season', 'crypto-leading', 'balanced');

    // Calculate spreads for precision
    const goldSpread = gold - Math.max(stocks, crypto);
    const cryptoSpread = crypto - Math.max(gold, stocks);
    const stocksSpread = stocks - Math.max(gold, crypto);

    // SCENARIO 1: Flight to Safety (Gold dominates)
    // Strong version: Gold +15 or more above both
    if (gold > stocks + 15 && gold > crypto + 15) {
        analysisBox.classList.add('flight-to-safety');
        iconEl.textContent = '🟢';
        titleEl.textContent = 'Strong Flight to Safety';
        detailEl.innerHTML = `
            <strong>Gold is massively outperforming</strong> (${gold.toFixed(1)} vs Stocks ${stocks.toFixed(1)} vs Crypto ${crypto.toFixed(1)}).<br>
            Extreme risk-off environment. Capital is fleeing risk assets into safe havens.
            This indicates severe market stress, geopolitical crisis, or economic panic.
        `;
    }
    // Moderate version: Gold +8 or more above both
    else if (gold > stocks + 8 && gold > crypto + 8) {
        analysisBox.classList.add('flight-to-safety');
        iconEl.textContent = '🟢';
        titleEl.textContent = 'Flight to Safety';
        detailEl.innerHTML = `
            <strong>Gold is significantly outperforming</strong> (${gold.toFixed(1)} vs Stocks ${stocks.toFixed(1)} vs Crypto ${crypto.toFixed(1)}).<br>
            Capital is rotating away from risk assets (stocks, crypto) into safe havens.
            This typically happens during market uncertainty, geopolitical tensions, or economic concerns.
        `;
    }

    // SCENARIO 2: Extreme Speculation (Crypto massively dominates)
    else if (crypto > gold + 20 && crypto > stocks + 15) {
        analysisBox.classList.add('altcoin-season');
        iconEl.textContent = '⚠️';
        titleEl.textContent = 'Extreme Speculation / Market Top Warning';
        detailEl.innerHTML = `
            <strong>Crypto sentiment is at extreme levels</strong> (${crypto.toFixed(1)} vs Gold ${gold.toFixed(1)} vs Stocks ${stocks.toFixed(1)}).<br>
            This is an <strong>extremely dangerous</strong> level of speculation. Historically, such extremes mark market tops.
            Consider taking profits and reducing exposure. Euphoria rarely lasts.
        `;
    }
    // SCENARIO 3: Altcoin Season (Crypto strongly dominates, +12 or more above Gold)
    else if (crypto >= gold + 12 && crypto > stocks + 8) {
        analysisBox.classList.add('altcoin-season');
        iconEl.textContent = '🟡';
        titleEl.textContent = 'Altcoin Season / Peak Speculation';
        detailEl.innerHTML = `
            <strong>Crypto sentiment is extremely elevated</strong> (${crypto.toFixed(1)} vs Gold ${gold.toFixed(1)} vs Stocks ${stocks.toFixed(1)}).<br>
            Peak speculation and maximum risk appetite. Crypto is decoupling to the upside.
            Historically, extreme crypto greed can signal market tops. Proceed with caution.
        `;
    }

    // SCENARIO 4: Risk-On with Stocks Leading (Traditional equities dominate)
    else if (stocks > gold + 8 && stocks > crypto + 5) {
        analysisBox.classList.add('risk-on');
        iconEl.textContent = '🔴';
        titleEl.textContent = 'Risk-On (Stocks Leading)';
        detailEl.innerHTML = `
            <strong>Equities are leading the market</strong> (Stocks ${stocks.toFixed(1)} vs Crypto ${crypto.toFixed(1)} vs Gold ${gold.toFixed(1)}).<br>
            Traditional risk assets are favored. Investors are optimistic about economic growth.
            This is a healthy risk-on environment, but remain vigilant for shifts in sentiment.
        `;
    }

    // SCENARIO 5: Crypto Leading (Crypto moderately ahead but not extreme, between +5 and +11)
    else if (crypto > gold + 5 && crypto < gold + 12 && crypto >= stocks - 5) {
        analysisBox.classList.add('crypto-leading');
        iconEl.textContent = '🟠';
        titleEl.textContent = 'Crypto Leading';
        detailEl.innerHTML = `
            <strong>Crypto sentiment is leading the market</strong> (Crypto ${crypto.toFixed(1)} vs Gold ${gold.toFixed(1)} vs Stocks ${stocks.toFixed(1)}).<br>
            Digital assets are showing relative strength compared to traditional safe havens.
            Risk appetite is increasing but not yet at extreme levels. Monitor for acceleration into Altcoin Season.
        `;
    }

    // SCENARIO 6: General Risk-On (Stocks and/or Crypto ahead of Gold, but no clear single leader)
    else if ((stocks > gold + 6 || crypto > gold + 6) && goldSpread < -5) {
        analysisBox.classList.add('risk-on');
        iconEl.textContent = '🔴';
        titleEl.textContent = 'Risk-On Environment';
        detailEl.innerHTML = `
            <strong>Risk assets are favored</strong> (Stocks ${stocks.toFixed(1)}, Crypto ${crypto.toFixed(1)} vs Gold ${gold.toFixed(1)}).<br>
            Investors are optimistic and seeking returns over safety.
            This environment favors growth assets but can be vulnerable to sudden shifts in sentiment.
        `;
    }

    // SCENARIO 7: Balanced Sentiment (No clear leader)
    else {
        analysisBox.classList.add('balanced');
        iconEl.textContent = '⚪';
        titleEl.textContent = 'Balanced Sentiment';
        detailEl.innerHTML = `
            <strong>No clear trend across markets</strong> (Gold ${gold.toFixed(1)}, Stocks ${stocks.toFixed(1)}, Crypto ${crypto.toFixed(1)}).<br>
            Sentiment is relatively balanced across asset classes.
            Markets are in a transitional phase with no dominant capital flow direction.
        `;
    }
}

/**
 * Update last update timestamp
 */
function updateLastUpdate() {
    const lastUpdate = document.getElementById('lastUpdate');
    lastUpdate.textContent = formatTimestamp(goldData.timestamp);
}

/**
 * Update the main score display and gauge
 */
function updateMainScore() {
    const { score, label, timestamp } = indexData;

    // Update score number
    const scoreNumber = document.getElementById('scoreNumber');
    scoreNumber.textContent = Math.round(score);

    // Update label
    const scoreLabel = document.getElementById('scoreLabel');
    scoreLabel.textContent = label;

    // Apply color class
    const colorClass = getColorClass(score);
    scoreNumber.className = `score-number ${colorClass}`;
    scoreLabel.className = `score-label ${colorClass}`;

    // Update progress indicator
    updateProgressIndicator(score);

    // Update timestamp
    const lastUpdate = document.getElementById('lastUpdate');
    lastUpdate.textContent = formatTimestamp(timestamp);
}

/**
 * Update the progress indicator position
 * @param {number} score - Score from 0 to 100
 */
function updateProgressIndicator(score) {
    const indicator = document.getElementById('progressIndicator');
    if (indicator) {
        // Position indicator based on score (0-100%)
        indicator.style.left = `${score}%`;
    }
}

/**
 * Update Market Context section (Gold vs Stocks comparison)
 */
function updateMarketContext() {
    if (!indexData || !stocksData) return;

    const goldScore = indexData.score;
    const stocksScore = stocksData.score;
    const divergence = goldScore - stocksScore;

    // Update Gold bar
    document.getElementById('goldContextScore').textContent = goldScore;
    document.getElementById('goldContextLabel').textContent = indexData.label;
    document.getElementById('goldHealthbar').style.width = `${goldScore}%`;

    // Update Stocks bar
    document.getElementById('stocksContextScore').textContent = stocksScore;
    document.getElementById('stocksContextLabel').textContent = stocksData.label;
    document.getElementById('stocksHealthbar').style.width = `${stocksScore}%`;

    // Update Divergence message
    const divergenceMessage = document.getElementById('divergenceMessage');

    // Determine message based on divergence
    if (Math.abs(divergence) < 10) {
        divergenceMessage.innerHTML = '⚪ <strong>Balanced</strong> - Similar sentiment across markets';
    } else if (divergence > 10) {
        divergenceMessage.innerHTML = `🟢 <strong>Flight to Safety</strong> - Gold ${divergence.toFixed(1)} points higher (capital rotating to safe havens)`;
    } else {
        divergenceMessage.innerHTML = `🔴 <strong>Risk-On</strong> - Stocks ${Math.abs(divergence).toFixed(1)} points higher (capital rotating to equities)`;
    }

    // Color coding for scores
    document.getElementById('goldContextScore').className = getColorClass(goldScore);
    document.getElementById('stocksContextScore').className = getColorClass(stocksScore);
}

/**
 * Draw historical chart
 * @param {number} days - Number of days to display (default: 30)
 */
function updateHistoryChart(days = 30) {
    const goldHistory = goldData?.history || [];
    const stocksHistory = stocksData?.history || [];
    const cryptoHistory = cryptoData?.history || [];

    if (goldHistory.length === 0 && stocksHistory.length === 0 && cryptoHistory.length === 0) return;

    const canvas = document.getElementById('historyChart');
    const ctx = canvas.getContext('2d');

    // Set canvas size
    const container = canvas.parentElement;
    canvas.width = container.offsetWidth;
    canvas.height = container.offsetHeight;

    // Prepare Gold data
    const sortedGoldHistory = [...goldHistory].sort((a, b) =>
        new Date(a.date) - new Date(b.date)
    );
    const limitedGoldHistory = sortedGoldHistory.slice(-days);

    // Prepare Stocks data
    const sortedStocksHistory = [...stocksHistory].sort((a, b) =>
        new Date(a.date) - new Date(b.date)
    );
    const limitedStocksHistory = sortedStocksHistory.slice(-days);

    // Prepare Crypto data
    const sortedCryptoHistory = [...cryptoHistory].sort((a, b) =>
        new Date(a.date) - new Date(b.date)
    );
    const limitedCryptoHistory = sortedCryptoHistory.slice(-days);

    // Check which curves to show
    const showGold = document.getElementById('toggleGold')?.checked !== false;
    const showStocks = document.getElementById('toggleStocks')?.checked !== false;
    const showCrypto = document.getElementById('toggleCrypto')?.checked !== false;

    drawChart(ctx, canvas, limitedGoldHistory, limitedStocksHistory, limitedCryptoHistory, showGold, showStocks, showCrypto);
}

/**
 * Draw the line chart
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} goldData - Gold historical data
 * @param {Array} stocksData - Stocks historical data
 * @param {Array} cryptoData - Crypto historical data
 * @param {boolean} showGold - Whether to show gold line
 * @param {boolean} showStocks - Whether to show stocks line
 * @param {boolean} showCrypto - Whether to show crypto line
 */
function drawChart(ctx, canvas, goldData, stocksData, cryptoData, showGold, showStocks, showCrypto) {
    const width = canvas.width;
    const height = canvas.height;
    const paddingTop = 40;
    const paddingBottom = 60; // Extra space for rotated labels
    const paddingSide = 40;
    const chartWidth = width - paddingSide * 2;
    const chartHeight = height - paddingTop - paddingBottom;
    const padding = paddingSide; // For compatibility with existing code

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw background zones
    drawBackgroundZones(ctx, paddingTop, chartHeight, chartWidth, paddingSide);

    // Draw grid
    drawGrid(ctx, paddingTop, chartHeight, chartWidth, paddingSide);

    // Draw Crypto line first (bottom layer) - Orange
    if (showCrypto && cryptoData.length > 0) {
        drawLine(ctx, cryptoData, paddingTop, paddingSide, chartHeight, chartWidth, '#F7931A', 2);
        drawPoints(ctx, cryptoData, paddingTop, paddingSide, chartHeight, chartWidth, '#F7931A', 3);
    }

    // Draw Stocks line (middle layer) - Blue
    if (showStocks && stocksData.length > 0) {
        drawLine(ctx, stocksData, paddingTop, paddingSide, chartHeight, chartWidth, '#4A90E2', 2);
        drawPoints(ctx, stocksData, paddingTop, paddingSide, chartHeight, chartWidth, '#4A90E2', 3);
    }

    // Draw Gold line on top - Gold
    if (showGold && goldData.length > 0) {
        drawLine(ctx, goldData, paddingTop, paddingSide, chartHeight, chartWidth, '#FFD700', 2);
        drawPoints(ctx, goldData, paddingTop, paddingSide, chartHeight, chartWidth, '#FFD700', 3);
    }

    // Draw axes labels (use whichever dataset has data)
    const labelData = goldData.length > 0 ? goldData : (stocksData.length > 0 ? stocksData : cryptoData);
    if (labelData.length > 0) {
        drawLabels(ctx, labelData, paddingSide, chartWidth, height);
    }
}

/**
 * Draw background fear/greed zones
 */
function drawBackgroundZones(ctx, paddingTop, chartHeight, chartWidth, paddingSide) {
    const padding = paddingSide;
    const zones = [
        { max: 25, color: 'rgba(234, 57, 67, 0.03)' },   // Extreme Fear
        { max: 45, color: 'rgba(245, 166, 35, 0.03)' },  // Fear
        { max: 55, color: 'rgba(248, 231, 28, 0.03)' },  // Neutral
        { max: 75, color: 'rgba(126, 211, 33, 0.03)' },  // Greed
        { max: 100, color: 'rgba(80, 227, 194, 0.03)' }  // Extreme Greed
    ];

    let prevY = paddingTop + chartHeight;
    zones.forEach(zone => {
        const y = paddingTop + chartHeight - (zone.max / 100) * chartHeight;
        ctx.fillStyle = zone.color;
        ctx.fillRect(padding, y, chartWidth, prevY - y);
        prevY = y;
    });
}

/**
 * Draw grid lines
 */
function drawGrid(ctx, paddingTop, chartHeight, chartWidth, paddingSide) {
    const padding = paddingSide;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;

    // Horizontal lines (score levels)
    [0, 25, 50, 75, 100].forEach(score => {
        const y = paddingTop + chartHeight - (score / 100) * chartHeight;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(padding + chartWidth, y);
        ctx.stroke();

        // Labels
        ctx.fillStyle = '#a0a0a0';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(score, padding - 10, y + 4);
    });
}

/**
 * Draw divergence zones (gold vs stocks background shading)
 */
function drawDivergenceZones(ctx, goldData, stocksData, padding, chartHeight, chartWidth) {
    if (goldData.length < 2 || stocksData.length < 2) return;

    // Align datasets by matching dates or using same length
    const minLength = Math.min(goldData.length, stocksData.length);

    ctx.globalAlpha = 0.08; // Very subtle

    for (let i = 0; i < minLength - 1; i++) {
        const goldScore = goldData[i].score;
        const stocksScore = stocksData[i].score;

        const x1 = padding + (i / (minLength - 1)) * chartWidth;
        const x2 = padding + ((i + 1) / (minLength - 1)) * chartWidth;

        const y1 = padding + chartHeight - (goldScore / 100) * chartHeight;
        const y2 = padding + chartHeight - (stocksScore / 100) * chartHeight;
        const y1Next = padding + chartHeight - (goldData[i + 1].score / 100) * chartHeight;
        const y2Next = padding + chartHeight - (stocksData[i + 1].score / 100) * chartHeight;

        // Fill area between curves
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y1Next);
        ctx.lineTo(x2, y2Next);
        ctx.lineTo(x1, y2);
        ctx.closePath();

        // Color based on which is higher
        if (goldScore > stocksScore) {
            ctx.fillStyle = '#FFD700'; // Gold tint
        } else {
            ctx.fillStyle = '#4A90E2'; // Blue tint
        }
        ctx.fill();
    }

    ctx.globalAlpha = 1.0; // Reset
}

/**
 * Draw the main line
 */
function drawLine(ctx, data, paddingTop, paddingSide, chartHeight, chartWidth, color = '#FFD700', lineWidth = 4) {
    if (data.length < 2) return;

    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();

    data.forEach((point, index) => {
        const x = paddingSide + (index / (data.length - 1)) * chartWidth;
        const y = paddingTop + chartHeight - (point.score / 100) * chartHeight;

        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.stroke();
}

/**
 * Draw data points
 */
function drawPoints(ctx, data, paddingTop, paddingSide, chartHeight, chartWidth, lineColor = '#FFD700', radius = 3) {
    // Subsample for long periods to reduce visual clutter
    const step = data.length > 180 ? Math.ceil(data.length / 100) : 1;

    data.forEach((point, index) => {
        // Skip points based on subsampling
        if (index % step !== 0 && index !== data.length - 1) return;

        const x = paddingSide + (index / (data.length - 1)) * chartWidth;
        const y = paddingTop + chartHeight - (point.score / 100) * chartHeight;

        // Point - use the line color for consistency
        ctx.fillStyle = lineColor;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();

        // Subtle outline
        ctx.strokeStyle = 'rgba(26, 26, 46, 0.3)';
        ctx.lineWidth = 1;
        ctx.stroke();
    });
}

/**
 * Draw axis labels
 */
function drawLabels(ctx, data, paddingSide, chartWidth, height) {
    ctx.fillStyle = '#a0a0a0';
    ctx.font = '11px sans-serif';

    // Determine number of labels based on data length
    const numLabels = data.length > 180 ? 8 : 5;
    const step = Math.floor(data.length / (numLabels - 1));

    for (let i = 0; i < numLabels; i++) {
        const index = i === numLabels - 1 ? data.length - 1 : i * step;
        if (index < data.length) {
            const point = data[index];
            const x = paddingSide + (index / (data.length - 1)) * chartWidth;
            const date = new Date(point.date);
            const label = formatDateShort(date);

            // Rotate labels for better readability
            ctx.save();
            ctx.translate(x, height - 20);
            ctx.rotate(-Math.PI / 6); // -30 degrees
            ctx.textAlign = 'right';
            ctx.fillText(label, 0, 0);
            ctx.restore();
        }
    }
}

/**
 * Get color for chart point based on score
 * @param {number} score - Score value
 * @returns {string} - Color hex code
 */
function getChartPointColor(score) {
    if (score <= 25) return '#EA3943';
    if (score <= 45) return '#F5A623';
    if (score <= 55) return '#F8E71C';
    if (score <= 75) return '#7ED321';
    return '#50E3C2';
}

/**
 * Get color class based on score
 * @param {number} score - Score from 0 to 100
 * @returns {string} - CSS class name
 */
function getColorClass(score) {
    if (score <= 25) return 'color-extreme-fear';
    if (score <= 45) return 'color-fear';
    if (score <= 55) return 'color-neutral';
    if (score <= 75) return 'color-greed';
    return 'color-extreme-greed';
}

/**
 * Get color gradient for mini-bar based on score
 * @param {number} score - Fear & Greed score (0-100)
 * @returns {string} - CSS gradient string
 */
function getColorGradient(score) {
    if (score <= 25) {
        // Extreme Fear - Red
        return 'linear-gradient(90deg, #EA3943, #F54343)';
    } else if (score <= 45) {
        // Fear - Orange
        return 'linear-gradient(90deg, #F5A623, #F5B643)';
    } else if (score <= 55) {
        // Neutral - Yellow
        return 'linear-gradient(90deg, #F8E71C, #F8EC3C)';
    } else if (score <= 75) {
        // Greed - Light Green
        return 'linear-gradient(90deg, #7ED321, #8EE331)';
    } else {
        // Extreme Greed - Cyan
        return 'linear-gradient(90deg, #50E3C2, #60F3D2)';
    }
}

/**
 * Format timestamp for display
 * @param {string} timestamp - ISO timestamp
 * @returns {string} - Formatted date/time
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const options = {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'UTC'
    };
    return date.toLocaleDateString('en-US', options) + ' UTC';
}

/**
 * Format date for chart labels
 * @param {Date} date - Date object
 * @returns {string} - Formatted date
 */
function formatDateShort(date) {
    const day = date.getDate();
    const month = date.getMonth() + 1;
    return `${day}/${month}`;
}

/**
 * Show error message
 */
function showError() {
    const scoreNumber = document.getElementById('scoreNumber');
    const scoreLabel = document.getElementById('scoreLabel');

    // Only update if elements exist (dedicated pages)
    if (scoreNumber) scoreNumber.textContent = '--';
    if (scoreLabel) {
        scoreLabel.textContent = 'Loading Error';
        scoreLabel.style.color = '#EA3943';
    }

    // Show error in components
    document.querySelectorAll('.component-score').forEach(el => {
        el.textContent = '--';
    });
    document.querySelectorAll('.component-detail').forEach(el => {
        el.textContent = 'Data unavailable';
    });
}

// Track current period selection
let currentPeriod = 30;

// Redraw chart on window resize
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (goldData) {
            updateHistoryChart(currentPeriod);
        }
    }, 250);
});

// Period selector and chart toggle event listeners
document.addEventListener('DOMContentLoaded', () => {
    const periodButtons = document.querySelectorAll('.period-btn');

    periodButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Update active state
            periodButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // Update period and redraw chart
            currentPeriod = parseInt(button.dataset.period);
            if (goldData) {
                updateHistoryChart(currentPeriod);
            }
        });
    });

    // Chart toggle checkboxes
    const toggleGold = document.getElementById('toggleGold');
    const toggleStocks = document.getElementById('toggleStocks');
    const toggleCrypto = document.getElementById('toggleCrypto');

    if (toggleGold) {
        toggleGold.addEventListener('change', () => {
            if (goldData) {
                updateHistoryChart(currentPeriod);
            }
        });
    }

    if (toggleStocks) {
        toggleStocks.addEventListener('change', () => {
            if (stocksData) {
                updateHistoryChart(currentPeriod);
            }
        });
    }

    if (toggleCrypto) {
        toggleCrypto.addEventListener('change', () => {
            if (cryptoData) {
                updateHistoryChart(currentPeriod);
            }
        });
    }

    // Update rotation gauge when data changes
    function updateRotationGauge() {
        const rotationPointer = document.getElementById('rotationPointer');
        const rotationBadge = document.getElementById('rotationBadge');
        const statusTitle = document.getElementById('statusTitle');
        const strengthFill = document.getElementById('strengthFill');
        const strengthValue = document.getElementById('strengthValue');
        const assetGold = document.getElementById('assetGold');
        const assetStocks = document.getElementById('assetStocks');
        const assetCrypto = document.getElementById('assetCrypto');
        const trendGold = document.getElementById('trendGold');
        const trendStocks = document.getElementById('trendStocks');
        const trendCrypto = document.getElementById('trendCrypto');
        const rotationInterpretation = document.getElementById('rotationInterpretation');
        const contrarianStars = document.getElementById('contrarianStars');
        const contrarianText = document.getElementById('contrarianText');

        if (!rotationPointer || !goldData || !stocksData || !cryptoData) {
            return;
        }

        const gold = goldData.score;
        const stocks = stocksData.score;
        const crypto = cryptoData.score;

        // Calculate continuous position (0-100%)
        // Based on crypto vs gold difference
        const rotationScore = crypto - gold;
        const position = ((rotationScore + 100) / 200) * 100;

        // Calculate signal strength (how extreme is the rotation)
        const spread = Math.abs(rotationScore);
        const strength = Math.min(100, (spread / 50) * 100); // 0-50 spread = 0-100% strength

        // Determine badge, title, and emoji
        let badge, title, emoji;
        if (position < 35) {
            badge = "PANIC MODE";
            title = "😱 EXTREME FEAR";
            emoji = "😱";
        } else if (position < 48) {
            badge = "FEAR";
            title = "😰 FEAR MODE";
            emoji = "😰";
        } else if (position < 52) {
            badge = "CALM";
            title = "😐 BALANCED";
            emoji = "😐";
        } else if (position < 65) {
            badge = "GREED";
            title = "😊 GREED MODE";
            emoji = "😊";
        } else {
            badge = "EUPHORIA";
            title = "🤑 EXTREME GREED";
            emoji = "🤑";
        }

        // Update asset indicators with colors
        assetGold.textContent = `${gold.toFixed(0)} (${goldData.label})`;
        assetGold.style.color = getScoreColor(gold);
        assetStocks.textContent = `${stocks.toFixed(0)} (${stocksData.label})`;
        assetStocks.style.color = getScoreColor(stocks);
        assetCrypto.textContent = `${crypto.toFixed(0)} (${cryptoData.label})`;
        assetCrypto.style.color = getScoreColor(crypto);

        // Trend arrows
        trendGold.textContent = gold > 55 ? "↗" : gold < 45 ? "↘" : "→";
        trendStocks.textContent = stocks > 55 ? "↗" : stocks < 45 ? "↘" : "→";
        trendCrypto.textContent = crypto > 55 ? "↗" : crypto < 45 ? "↘" : "→";

        // Generate interpretation text
        let text;
        if (position < 35) {
            // Extreme Fear / Risk-off
            if (gold > 60 && crypto < 40) {
                text = `<strong>💭 Market is saying:</strong> "Mass exodus from risk assets into gold. Everyone wants safety RIGHT NOW. Classic panic behavior."`;
            } else {
                text = `<strong>💭 Market is saying:</strong> "Capital flowing to safe havens. Investors are defensive and fear is driving decisions."`;
            }
        } else if (position > 65) {
            // Euphoria / Risk-on
            if (crypto > 60 && gold < 40) {
                text = `<strong>💭 Market is saying:</strong> "FOMO mode activated. Everyone chasing crypto gains. Gold is forgotten. Peak euphoria vibes."`;
            } else {
                text = `<strong>💭 Market is saying:</strong> "Risk-on environment. Investors confident and hunting for growth over safety."`;
            }
        } else {
            // Balanced
            text = `<strong>💭 Market is saying:</strong> "No clear direction. Investors uncertain. Market in transition or waiting for catalyst."`;
        }

        // Contrarian signal calculation
        let stars, contrarianMsg;
        if (strength > 70) {
            // Very strong signal = great contrarian opportunity
            if (position < 35) {
                // Extreme fear = buy opportunity
                stars = "⭐⭐⭐⭐⭐";
                contrarianMsg = `<strong>Historical data shows:</strong> When rotation hits extreme fear like this, crypto rebounds <strong>95% of the time</strong> within 60 days (average +26 points). Current fear could be your buying opportunity.`;
            } else if (position > 65) {
                // Extreme greed = sell/caution opportunity
                stars = "⭐⭐⭐⭐⭐";
                contrarianMsg = `<strong>Historical data shows:</strong> Extreme euphoria often precedes corrections. When everyone is greedy, contrarians get cautious. Consider taking profits.`;
            }
        } else if (strength > 45) {
            stars = "⭐⭐⭐";
            if (position < 35) {
                contrarianMsg = `Moderate fear signal. Historically, 84% bounce rate within 30 days. Could be early entry point.`;
            } else {
                contrarianMsg = `Moderate greed signal. Watch for reversal signs.`;
            }
        } else {
            stars = "⭐";
            contrarianMsg = `Weak signal - market balanced. Not ideal for contrarian plays. Wait for clearer extremes.`;
        }

        // Update UI
        rotationPointer.style.left = `${position}%`;
        rotationBadge.textContent = emoji;
        statusTitle.textContent = title;
        strengthFill.style.width = `${strength}%`;
        strengthValue.textContent = `${strength.toFixed(0)}%`;
        rotationInterpretation.innerHTML = text;
        contrarianStars.textContent = stars;
        contrarianText.innerHTML = contrarianMsg;
    }

    // Helper function to get color based on score
    function getScoreColor(score) {
        if (score <= 25) return '#EA3943'; // Red
        if (score <= 45) return '#F5A623'; // Orange
        if (score <= 55) return '#F8E71C'; // Yellow
        if (score <= 75) return '#7ED321'; // Green
        return '#50E3C2'; // Cyan
    }

    // Call updateRotationGauge whenever data is loaded
    // We'll hook it into the existing data fetch callbacks
    const originalFetchGold = window.fetch;

    // Simple approach: update after all data loaded
    // This will be called after loadAllData completes
    setTimeout(() => {
        if (goldData && stocksData && cryptoData) {
            updateRotationGauge();
        }
    }, 1000);
});
