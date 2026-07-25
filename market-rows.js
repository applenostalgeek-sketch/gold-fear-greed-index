// "Across all markets": hydrate the static skeleton with live scores.
// The markup is crawlable and the links work without JS; this only fills in
// scores, colors and bars. Shared by gold/bonds/stocks/crypto — the current
// page is derived from the active row, so there is nothing to configure.
// Requires getColor() from shared.js (loaded before this file).
(function () {
    function zn(s) { if (s <= 25) return 'Extreme Fear'; if (s <= 45) return 'Fear'; if (s <= 55) return 'Neutral'; if (s <= 75) return 'Greed'; return 'Extreme Greed'; }
    var root = document.getElementById('marketRows');
    if (!root) return;

    // Which asset page are we on? The "You are here" row already says so.
    var activeRow = root.querySelector('.mrow.active');
    var fromPage = activeRow ? activeRow.dataset.market : 'unknown';

    root.querySelectorAll('[data-dest]').forEach(function (el) {
        el.addEventListener('click', function () {
            if (typeof gtag === 'function') {
                gtag('event', 'market_rows_click', { event_category: 'market_rows', event_label: el.dataset.dest, from_page: fromPage });
            }
        });
    });

    var files = { gold: 'data/gold-fear-greed.json', stocks: 'data/stocks-fear-greed.json', bonds: 'data/bonds-fear-greed.json', crypto: 'data/crypto-fear-greed.json' };
    Promise.all(Object.keys(files).map(function (k) {
        return fetch(files[k]).then(function (r) { return r.json(); }).then(function (d) { return [k, Math.round(d.score)]; });
    })).then(function (entries) {
        var s = {};
        entries.forEach(function (e) { s[e[0]] = e[1]; });
        function hydrate(key, v) {
            var row = root.querySelector('[data-market="' + key + '"]');
            if (!row) return;
            var c = getColor(v);
            var score = row.querySelector('.mrow-score');
            score.textContent = v; score.style.color = c;
            var badge = row.querySelector('.mrow-badge');
            badge.textContent = zn(v); badge.style.color = c; badge.style.background = c + '1f'; badge.style.display = '';
            var dot = row.querySelector('.mrow-dot');
            dot.style.background = c; dot.style.visibility = '';
            var fill = row.querySelector('.mrow-fill');
            requestAnimationFrame(function () { fill.style.setProperty('--score', v + '%'); dot.style.left = v + '%'; });
        }
        ['gold', 'stocks', 'bonds', 'crypto'].forEach(function (k) { hydrate(k, s[k]); });
        var comp = Math.round((s.gold + s.stocks + s.bonds + s.crypto) / 4), cc = getColor(comp);
        var foot = root.querySelector('.mrows-foot');
        var fv = foot.querySelector('.foot-val'), fz = foot.querySelector('.foot-zone');
        fv.textContent = comp; fv.style.color = cc;
        fz.textContent = zn(comp); fz.style.color = cc;
        foot.querySelectorAll('.logo-dots2 i').forEach(function (i) { i.style.background = cc; });
    }).catch(function () { /* skeleton stays: links keep working without data */ });
})();
