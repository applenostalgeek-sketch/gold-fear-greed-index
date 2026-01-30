// Gold Fear & Greed Index - Frontend JavaScript

// Configuration
const GOLD_DATA_URL = 'data/gold-fear-greed.json';
const STOCKS_DATA_URL = 'data/stocks-fear-greed.json';

// Global state
let indexData = null;
let stocksData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
});

/**
 * Load both Gold and Stocks index data
 */
async function loadAllData() {
    try {
        // Load both indices in parallel
        const [goldResponse, stocksResponse] = await Promise.all([
            fetch(GOLD_DATA_URL),
            fetch(STOCKS_DATA_URL)
        ]);

        if (!goldResponse.ok || !stocksResponse.ok) {
            throw new Error('HTTP error loading data');
        }

        indexData = await goldResponse.json();
        stocksData = await stocksResponse.json();

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
    if (!indexData) return;

    updateMainScore();
    updateMarketContext();
    updateComponents();
    updateHistoryChart();
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

    // Update Gold card
    document.getElementById('goldContextScore').textContent = goldScore;
    document.getElementById('goldContextLabel').textContent = indexData.label;
    document.getElementById('goldMiniIndicator').style.left = `${goldScore}%`;

    // Update Stocks card
    document.getElementById('stocksContextScore').textContent = stocksScore;
    document.getElementById('stocksContextLabel').textContent = stocksData.label;
    document.getElementById('stocksMiniIndicator').style.left = `${stocksScore}%`;

    // Update Divergence display
    const divergenceValue = document.getElementById('divergenceValue');
    const divergenceMessage = document.getElementById('divergenceMessage');
    const divergenceIcon = document.querySelector('.divergence-icon');

    divergenceValue.textContent = `${divergence > 0 ? '+' : ''}${divergence.toFixed(1)}`;

    // Determine message based on divergence
    if (Math.abs(divergence) < 10) {
        divergenceIcon.textContent = '⚪';
        divergenceMessage.textContent = 'Balanced sentiment across markets';
    } else if (divergence > 10) {
        divergenceIcon.textContent = '🟢';
        divergenceMessage.textContent = 'Flight to safety - Capital rotating to gold';
    } else {
        divergenceIcon.textContent = '🔴';
        divergenceMessage.textContent = 'Risk-on - Capital rotating to equities';
    }

    // Color coding for scores
    document.getElementById('goldContextScore').className = `index-score-number ${getColorClass(goldScore)}`;
    document.getElementById('stocksContextScore').className = `index-score-number ${getColorClass(stocksScore)}`;
}

/**
 * Update all component cards
 */
function updateComponents() {
    const { components } = indexData;

    Object.keys(components).forEach(key => {
        const component = components[key];
        updateComponentCard(key, component);
    });
}

/**
 * Update a single component card
 * @param {string} key - Component key
 * @param {object} data - Component data
 */
function updateComponentCard(key, data) {
    const { score, detail } = data;

    // Update score
    const scoreElement = document.getElementById(`${key}-score`);
    if (scoreElement) {
        scoreElement.textContent = Math.round(score);
        scoreElement.className = `component-score ${getColorClass(score)}`;
    }

    // Update detail
    const detailElement = document.getElementById(`${key}-detail`);
    if (detailElement) {
        detailElement.textContent = detail;
    }

    // Update bar
    const barElement = document.getElementById(`${key}-bar`);
    if (barElement) {
        barElement.style.width = `${score}%`;
    }
}

/**
 * Draw historical chart
 * @param {number} days - Number of days to display (default: 30)
 */
function updateHistoryChart(days = 30) {
    const history = indexData.history || [];
    if (history.length === 0) return;

    const canvas = document.getElementById('historyChart');
    const ctx = canvas.getContext('2d');

    // Set canvas size
    const container = canvas.parentElement;
    canvas.width = container.offsetWidth;
    canvas.height = container.offsetHeight;

    // Prepare data (reverse to show oldest first)
    const sortedHistory = [...history].sort((a, b) =>
        new Date(a.date) - new Date(b.date)
    );

    // Limit to last N days
    const limitedHistory = sortedHistory.slice(-days);

    drawChart(ctx, canvas, limitedHistory);
}

/**
 * Draw the line chart
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} data - Historical data
 */
function drawChart(ctx, canvas, data) {
    const width = canvas.width;
    const height = canvas.height;
    const padding = 40;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw background zones
    drawBackgroundZones(ctx, padding, chartHeight, chartWidth);

    // Draw grid
    drawGrid(ctx, padding, chartHeight, chartWidth);

    // Draw line
    drawLine(ctx, data, padding, chartHeight, chartWidth);

    // Draw points
    drawPoints(ctx, data, padding, chartHeight, chartWidth);

    // Draw axes labels
    drawLabels(ctx, data, padding, chartHeight, chartWidth, height);
}

/**
 * Draw background fear/greed zones
 */
function drawBackgroundZones(ctx, padding, chartHeight, chartWidth) {
    const zones = [
        { max: 25, color: 'rgba(234, 57, 67, 0.1)' },   // Extreme Fear
        { max: 45, color: 'rgba(245, 166, 35, 0.1)' },  // Fear
        { max: 55, color: 'rgba(248, 231, 28, 0.1)' },  // Neutral
        { max: 75, color: 'rgba(126, 211, 33, 0.1)' },  // Greed
        { max: 100, color: 'rgba(80, 227, 194, 0.1)' }  // Extreme Greed
    ];

    let prevY = padding + chartHeight;
    zones.forEach(zone => {
        const y = padding + chartHeight - (zone.max / 100) * chartHeight;
        ctx.fillStyle = zone.color;
        ctx.fillRect(padding, y, chartWidth, prevY - y);
        prevY = y;
    });
}

/**
 * Draw grid lines
 */
function drawGrid(ctx, padding, chartHeight, chartWidth) {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;

    // Horizontal lines (score levels)
    [0, 25, 50, 75, 100].forEach(score => {
        const y = padding + chartHeight - (score / 100) * chartHeight;
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
 * Draw the main line
 */
function drawLine(ctx, data, padding, chartHeight, chartWidth) {
    if (data.length < 2) return;

    ctx.strokeStyle = '#FFD700';
    ctx.lineWidth = 3;
    ctx.beginPath();

    data.forEach((point, index) => {
        const x = padding + (index / (data.length - 1)) * chartWidth;
        const y = padding + chartHeight - (point.score / 100) * chartHeight;

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
function drawPoints(ctx, data, padding, chartHeight, chartWidth) {
    data.forEach((point, index) => {
        const x = padding + (index / (data.length - 1)) * chartWidth;
        const y = padding + chartHeight - (point.score / 100) * chartHeight;

        // Point
        ctx.fillStyle = getChartPointColor(point.score);
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();

        // Outline
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
    });
}

/**
 * Draw axis labels
 */
function drawLabels(ctx, data, padding, chartHeight, chartWidth, height) {
    ctx.fillStyle = '#a0a0a0';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';

    // Show date labels for first, middle, and last points
    const showIndices = [
        0,
        Math.floor(data.length / 2),
        data.length - 1
    ];

    showIndices.forEach(index => {
        if (index < data.length) {
            const point = data[index];
            const x = padding + (index / (data.length - 1)) * chartWidth;
            const date = new Date(point.date);
            const label = formatDateShort(date);
            ctx.fillText(label, x, height - padding + 20);
        }
    });
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

    scoreNumber.textContent = '--';
    scoreLabel.textContent = 'Loading Error';
    scoreLabel.style.color = '#EA3943';

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
        if (indexData) {
            updateHistoryChart(currentPeriod);
        }
    }, 250);
});

// Period selector event listeners
document.addEventListener('DOMContentLoaded', () => {
    const periodButtons = document.querySelectorAll('.period-btn');

    periodButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Update active state
            periodButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // Update period and redraw chart
            currentPeriod = parseInt(button.dataset.period);
            if (indexData) {
                updateHistoryChart(currentPeriod);
            }
        });
    });
});
