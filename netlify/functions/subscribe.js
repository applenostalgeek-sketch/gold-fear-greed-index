// Netlify Function: subscribe a contact to the alert list
// Preferences stored in first_name as comma-separated list (Resend properties API doesn't work)
exports.handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': 'https://onoff.markets',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json',
  };

  // Handle CORS preflight
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers };
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  try {
    const { email, gold, stocks, bonds, crypto, sentiment } = JSON.parse(event.body);

    if (!email || !email.includes('@')) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Valid email required' }) };
    }

    const RESEND_API_KEY = process.env.RESEND_API_KEY;
    const AUDIENCE_ID = process.env.RESEND_AUDIENCE_ID;

    if (!RESEND_API_KEY || !AUDIENCE_ID) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'Server configuration error' }) };
    }

    const emailNorm = email.toLowerCase().trim();

    // Build preferences string: comma-separated list of selected assets
    const selected = [
      gold !== false && 'gold',
      stocks !== false && 'stocks',
      bonds !== false && 'bonds',
      crypto !== false && 'crypto',
      sentiment !== false && 'sentiment',
    ].filter(Boolean);

    // Create contact in Resend audience
    const response = await fetch(`https://api.resend.com/audiences/${AUDIENCE_ID}/contacts`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: emailNorm,
        first_name: selected.join(','),
        unsubscribed: false,
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      return { statusCode: response.status, headers, body: JSON.stringify({ error: result.message || 'Subscription failed' }) };
    }

    // Always PATCH to update preferences (POST doesn't update existing contacts)
    await fetch(`https://api.resend.com/audiences/${AUDIENCE_ID}/contacts/${result.id}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        first_name: selected.join(','),
        unsubscribed: false,
      }),
    });

    // Send welcome email
    const selectedLabels = [
      gold !== false && 'Gold',
      stocks !== false && 'Stocks',
      bonds !== false && 'Bonds',
      crypto !== false && 'Crypto',
      sentiment !== false && 'Market Sentiment',
    ].filter(Boolean);

    try {
      await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${RESEND_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'OnOff.Markets <newsletter@onoff.markets>',
          to: emailNorm,
          subject: "You're subscribed to OnOff.Markets alerts",
          html: `<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px;">
  <h2 style="color:#111;font-size:1.2rem;margin-bottom:16px;">You're in.</h2>
  <p style="line-height:1.6;font-size:0.95rem;color:#333;">You'll receive alerts when sentiment shifts significantly on: <strong>${selectedLabels.join(', ')}</strong>.</p>
  <p style="line-height:1.6;font-size:0.95rem;color:#333;margin-top:12px;">Expect a few emails per month — only when something meaningful moves.</p>
  <p style="margin-top:24px;font-size:0.85rem;color:#999;">— <a href="https://onoff.markets" style="color:#666;text-decoration:none;">OnOff.Markets</a></p>
  <p style="margin-top:24px;font-size:0.75rem;color:#999;">To unsubscribe, click "Alerts" on the site and use the unsubscribe option.</p>
</div>`,
        }),
      });
    } catch (_) {
      // Welcome email is non-critical
    }

    return { statusCode: 200, headers, body: JSON.stringify({ success: true, id: result.id }) };

  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Server error' }) };
  }
};
