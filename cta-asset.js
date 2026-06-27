/* cta-asset.js — inline alert CTA on asset pages.
   Subscribes to THIS asset only (derived from ASSET_CONFIG), and makes the
   shared modal pre-check only this asset via window.ALERT_CONTEXT.
   Must load after asset config is set and after alert-signup.js. */
(function () {
    var cfg = window.ASSET_CONFIG;
    if (!cfg || !cfg.dataUrl) return;
    var m = cfg.dataUrl.match(/([^/]+)-fear-greed/);
    var asset = m ? m[1] : null;
    if (!asset) return;

    // Tell the shared modal to pre-check only this asset (nav button + customize)
    window.ALERT_CONTEXT = [asset];

    var form = document.getElementById('ctaForm');
    var customize = document.getElementById('ctaCustomize');

    if (customize) {
        customize.addEventListener('click', function () {
            if (typeof window.openAlertPopup === 'function') {
                window.openAlertPopup();
            } else {
                var ov = document.getElementById('alertOverlay');
                if (ov) ov.classList.add('active');
            }
        });
    }

    if (!form) return;
    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        var email = document.getElementById('ctaEmail').value.trim();
        var btn = document.getElementById('ctaSubmit');
        var msg = document.getElementById('ctaMsg');
        if (!email || !email.includes('@')) {
            msg.textContent = 'Please enter a valid email.';
            msg.className = 'cta-msg error';
            return;
        }
        btn.disabled = true;
        btn.textContent = 'Subscribing...';
        msg.textContent = '';
        msg.className = 'cta-msg';

        // Asset-only preferences
        var prefs = { sentiment: false, gold: false, stocks: false, bonds: false, crypto: false };
        prefs[asset] = true;

        try {
            var res = await fetch('/.netlify/functions/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(Object.assign({ email: email }, prefs)),
            });
            if (res.ok) {
                msg.textContent = "You're in! You'll be alerted when " + (cfg.name || asset) + " sentiment shifts.";
                msg.className = 'cta-msg success';
                document.getElementById('ctaEmail').value = '';
                if (typeof gtag === 'function') {
                    gtag('event', 'alert_subscribe', { event_category: 'alerts', event_label: asset, signup_location: 'asset_cta' });
                }
            } else {
                var data = await res.json();
                msg.textContent = (data && data.error) || 'Something went wrong. Please try again.';
                msg.className = 'cta-msg error';
            }
        } catch (err) {
            msg.textContent = 'Network error. Please try again.';
            msg.className = 'cta-msg error';
        }

        btn.disabled = false;
        btn.textContent = 'Subscribe';
    });
})();
