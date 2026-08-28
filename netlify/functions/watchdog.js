// Netlify Scheduled Function: make sure today's index run actually happened.
//
// GitHub's scheduled workflows are best-effort. On 2026-08-27 and 2026-08-28 the
// daily cron simply never fired — no run was created, nothing failed — after 210
// consecutive successful days. All three of this account's repos were affected at
// once, with delays jumping from ~30 min to 5-11 hours. This function is the
// independent second opinion: it lives at Netlify, not GitHub, so a GitHub
// scheduler outage cannot take it down with it.
//
// It is a watchdog, not a second scheduler: it reads first and only acts when
// today's data is genuinely missing. On a normal day it does nothing at all.
//
// Schedule is declared in netlify.toml under [functions."watchdog"].

const OWNER = process.env.GH_OWNER || 'applenostalgeek-sketch';
const REPO = process.env.GH_REPO || 'gold-fear-greed-index';
const WORKFLOW = 'update-index.yml';
const ASSETS = ['gold', 'stocks', 'bonds', 'crypto'];

const todayUTC = () => new Date().toISOString().slice(0, 10);

// Read the newest date published for one asset. Cache-busted: /data/* is served
// with a 5-minute Cache-Control, which is exactly the window we must not trust.
async function latestDate(asset) {
  const url = `https://onoff.markets/data/${asset}-fear-greed.json?t=${Date.now()}`;
  const res = await fetch(url, { headers: { 'Cache-Control': 'no-cache' } });
  if (!res.ok) throw new Error(`${asset}: HTTP ${res.status}`);
  const body = await res.json();
  const history = body.history || [];
  if (!history.length) throw new Error(`${asset}: empty history`);
  return history.reduce((max, e) => (e.date > max ? e.date : max), history[0].date);
}

async function triggerWorkflow(token) {
  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main' }),
    }
  );
  // A successful dispatch returns 204 with no body.
  if (res.status !== 204) {
    throw new Error(`dispatch failed: HTTP ${res.status} ${await res.text()}`);
  }
}

async function notify(subject, lines) {
  const key = process.env.RESEND_API_KEY;
  const to = process.env.WATCHDOG_EMAIL;
  if (!key || !to) return; // notification is optional, never blocks the fix
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: 'OnOff.Markets <newsletter@onoff.markets>',
      to,
      subject,
      html:
        `<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:520px;margin:0 auto;padding:32px;">` +
        lines.map((l) => `<p style="line-height:1.6;font-size:0.95rem;color:#333;">${l}</p>`).join('') +
        `<p style="margin-top:24px;font-size:0.8rem;color:#999;">Sent by the Netlify watchdog, not by the daily job.</p></div>`,
    }),
  });
}

exports.handler = async () => {
  const today = todayUTC();

  let dates;
  try {
    dates = await Promise.all(ASSETS.map(latestDate));
  } catch (err) {
    // If the site itself is unreachable we cannot tell stale from broken.
    // Say so rather than firing a run blindly.
    await notify('OnOff watchdog: cannot read the site', [
      `The watchdog could not read the published data: <strong>${err.message}</strong>`,
      'No workflow was triggered. Worth a look.',
    ]);
    return { statusCode: 200, body: `unreadable: ${err.message}` };
  }

  const stale = ASSETS.filter((_, i) => dates[i] !== today);

  if (stale.length === 0) {
    return { statusCode: 200, body: `ok: all four up to date (${today})` };
  }

  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) {
    await notify('OnOff watchdog: data is stale and I cannot fix it', [
      `Missing today's entry (${today}) for: <strong>${stale.join(', ')}</strong>.`,
      'GH_DISPATCH_TOKEN is not set on Netlify, so the run could not be triggered.',
    ]);
    return { statusCode: 500, body: 'stale but GH_DISPATCH_TOKEN missing' };
  }

  try {
    await triggerWorkflow(token);
  } catch (err) {
    await notify('OnOff watchdog: could not trigger the run', [
      `Missing today's entry (${today}) for: <strong>${stale.join(', ')}</strong>.`,
      `Triggering the workflow failed: <strong>${err.message}</strong>`,
    ]);
    return { statusCode: 500, body: err.message };
  }

  await notify("OnOff watchdog: GitHub missed today's run, I started it", [
    `The scheduled run did not happen. Newest entry was ${dates[0]}, expected ${today}.`,
    `Assets missing today: <strong>${stale.join(', ')}</strong>.`,
    'The workflow has been triggered manually and should publish within a few minutes.',
  ]);

  return { statusCode: 200, body: `triggered: ${stale.join(',')}` };
};
