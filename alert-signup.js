/* alert-signup.js — Shared newsletter signup popup */

(function () {
    // Inject HTML
    const html = `
    <div class="alert-overlay" id="alertOverlay">
        <div class="alert-popup">
            <button class="close-btn" id="alertClose">&times;</button>
            <div id="alertFormView">
                <h3>Get Market Alerts</h3>
                <p class="subtitle">Receive alerts when sentiment shifts significantly.</p>
                <input type="email" id="alertEmail" placeholder="your@email.com" autocomplete="email">
                <div class="alert-checkboxes">
                    <label><input type="checkbox" name="sentiment" checked> Sentiment</label>
                    <label><input type="checkbox" name="gold" checked> Gold</label>
                    <label><input type="checkbox" name="stocks" checked> Stocks</label>
                    <label><input type="checkbox" name="bonds" checked> Bonds</label>
                    <label><input type="checkbox" name="crypto" checked> Crypto</label>
                </div>
                <button class="alert-submit" id="alertSubmit">Subscribe</button>
                <p class="alert-message" id="alertMsg"></p>
                <div class="alert-unsubscribe">
                    <a id="alertUnsubLink">Unsubscribe</a>
                </div>
            </div>
            <div id="alertUnsubView" style="display:none;">
                <h3>Unsubscribe</h3>
                <p class="subtitle">Enter your email to unsubscribe from all alerts.</p>
                <input type="email" id="alertUnsubEmail" placeholder="your@email.com" autocomplete="email">
                <button class="alert-submit" id="alertUnsubSubmit">Unsubscribe</button>
                <p class="alert-message" id="alertUnsubMsg"></p>
                <div class="alert-unsubscribe">
                    <a id="alertBackLink">Back to subscribe</a>
                </div>
            </div>
        </div>
    </div>`;

    document.body.insertAdjacentHTML('beforeend', html);

    // Elements
    const overlay = document.getElementById('alertOverlay');
    const closeBtn = document.getElementById('alertClose');
    const formView = document.getElementById('alertFormView');
    const unsubView = document.getElementById('alertUnsubView');
    const emailInput = document.getElementById('alertEmail');
    const submitBtn = document.getElementById('alertSubmit');
    const msg = document.getElementById('alertMsg');
    const unsubLink = document.getElementById('alertUnsubLink');
    const backLink = document.getElementById('alertBackLink');
    const unsubEmail = document.getElementById('alertUnsubEmail');
    const unsubSubmit = document.getElementById('alertUnsubSubmit');
    const unsubMsg = document.getElementById('alertUnsubMsg');

    // Open popup
    function openPopup() {
        overlay.classList.add('active');
        formView.style.display = '';
        unsubView.style.display = 'none';
        msg.textContent = '';
        msg.className = 'alert-message';
    }

    // Close popup
    function closePopup() {
        overlay.classList.remove('active');
    }

    // Bind open buttons (any element with class alert-btn)
    document.querySelectorAll('.alert-btn').forEach(function (btn) {
        btn.addEventListener('click', openPopup);
    });

    closeBtn.addEventListener('click', closePopup);
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) closePopup();
    });

    // Toggle subscribe/unsubscribe views
    unsubLink.addEventListener('click', function () {
        formView.style.display = 'none';
        unsubView.style.display = '';
        unsubMsg.textContent = '';
        unsubMsg.className = 'alert-message';
    });

    backLink.addEventListener('click', function () {
        formView.style.display = '';
        unsubView.style.display = 'none';
    });

    // Subscribe
    submitBtn.addEventListener('click', async function () {
        var email = emailInput.value.trim();
        if (!email || !email.includes('@')) {
            msg.textContent = 'Please enter a valid email.';
            msg.className = 'alert-message error';
            return;
        }

        var checkboxes = formView.querySelectorAll('input[type="checkbox"]');
        var prefs = {};
        checkboxes.forEach(function (cb) {
            prefs[cb.name] = cb.checked;
        });

        submitBtn.disabled = true;
        submitBtn.textContent = 'Subscribing...';
        msg.textContent = '';

        try {
            var res = await fetch('/.netlify/functions/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, ...prefs }),
            });
            var data = await res.json();

            if (res.ok) {
                msg.textContent = 'You\'re subscribed! You\'ll receive alerts when sentiment shifts.';
                msg.className = 'alert-message success';
                emailInput.value = '';
            } else {
                msg.textContent = data.error || 'Something went wrong. Please try again.';
                msg.className = 'alert-message error';
            }
        } catch (err) {
            msg.textContent = 'Network error. Please try again.';
            msg.className = 'alert-message error';
        }

        submitBtn.disabled = false;
        submitBtn.textContent = 'Subscribe';
    });

    // Unsubscribe
    unsubSubmit.addEventListener('click', async function () {
        var email = unsubEmail.value.trim();
        if (!email || !email.includes('@')) {
            unsubMsg.textContent = 'Please enter a valid email.';
            unsubMsg.className = 'alert-message error';
            return;
        }

        unsubSubmit.disabled = true;
        unsubSubmit.textContent = 'Processing...';
        unsubMsg.textContent = '';

        try {
            var res = await fetch('/.netlify/functions/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email }),
            });
            var data = await res.json();

            if (res.ok) {
                unsubMsg.textContent = 'You\'ve been unsubscribed. You won\'t receive further alerts.';
                unsubMsg.className = 'alert-message success';
                unsubEmail.value = '';
            } else {
                unsubMsg.textContent = data.error || 'Something went wrong.';
                unsubMsg.className = 'alert-message error';
            }
        } catch (err) {
            unsubMsg.textContent = 'Network error. Please try again.';
            unsubMsg.className = 'alert-message error';
        }

        unsubSubmit.disabled = false;
        unsubSubmit.textContent = 'Unsubscribe';
    });

    // ESC key to close
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay.classList.contains('active')) {
            closePopup();
        }
    });
})();
