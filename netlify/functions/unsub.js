// Netlify Function: unsubscribe from the link at the bottom of every alert email.
//
// The link carries the subscriber's Resend contact id (a random UUID, never the
// email address). GET only shows a confirmation button: mail scanners and link
// previews open links on their own, and must not unsubscribe anyone. The button
// POSTs back here, and so does the mail client's own "Unsubscribe" button
// (List-Unsubscribe-Post, RFC 8058). Either POST marks the contact unsubscribed,
// the same flag the site's form sets and send_alerts.py skips.
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const page = (title, body) => ({
  statusCode: 200,
  headers: { 'Content-Type': 'text/html; charset=utf-8', 'X-Robots-Tag': 'noindex' },
  body: `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>${title} - OnOff.Markets</title></head>
<body style="margin:0;background:#0a0a0a;color:#e4e4e7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:420px;margin:0 auto;padding:72px 20px;text-align:center;">
<div style="font-size:18px;font-weight:800;margin-bottom:36px;">On <span style="color:#d4a017;">&#9679;&#9679;</span> Off<span style="color:#71717a;">.Markets</span></div>
${body}
</div></body></html>`,
});

exports.handler = async (event) => {
  const id = (event.queryStringParameters || {}).c || '';
  if (!UUID.test(id)) {
    return page('Unsubscribe', `<p style="line-height:1.6;color:#a1a1aa;">This link is not valid.
      You can unsubscribe from <a href="https://onoff.markets/" style="color:#e4e4e7;">onoff.markets</a> &rarr; Alerts.</p>`);
  }

  if (event.httpMethod === 'GET') {
    return page('Unsubscribe', `<h1 style="font-size:22px;margin:0 0 12px;">Stop the alert emails?</h1>
      <p style="line-height:1.6;color:#a1a1aa;margin:0 0 28px;">You will no longer receive OnOff.Markets alerts.</p>
      <form method="POST" action="/.netlify/functions/unsub?c=${id}">
        <button type="submit" style="background:#e4e4e7;color:#0a0a0a;border:0;border-radius:8px;padding:12px 22px;font-size:15px;font-weight:600;cursor:pointer;">Unsubscribe</button>
      </form>`);
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }

  const RESEND_API_KEY = process.env.RESEND_API_KEY;
  const AUDIENCE_ID = process.env.RESEND_AUDIENCE_ID;
  if (!RESEND_API_KEY || !AUDIENCE_ID) {
    return page('Unsubscribe', `<p style="color:#a1a1aa;">Something went wrong on our side. Please reply to any alert email and we will remove you.</p>`);
  }

  try {
    const res = await fetch(`https://api.resend.com/audiences/${AUDIENCE_ID}/contacts/${id}`, {
      method: 'PATCH',
      headers: { 'Authorization': `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ unsubscribed: true }),
    });
    // An unknown id gets the same answer as a known one: the page reveals nothing.
    if (!res.ok && res.status !== 404) throw new Error(`Resend ${res.status}`);
  } catch (err) {
    return page('Unsubscribe', `<p style="color:#a1a1aa;">Something went wrong on our side. Please reply to any alert email and we will remove you.</p>`);
  }

  return page('Unsubscribed', `<h1 style="font-size:22px;margin:0 0 12px;">You're unsubscribed</h1>
    <p style="line-height:1.6;color:#a1a1aa;">No more alert emails. You can sign up again anytime on
    <a href="https://onoff.markets/" style="color:#e4e4e7;">onoff.markets</a>.</p>`);
};
