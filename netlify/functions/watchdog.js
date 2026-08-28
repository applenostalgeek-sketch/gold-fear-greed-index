// Netlify Scheduled Function: make sure today's index run and tweet happened.
//
// GitHub's scheduled workflows are best-effort. Between 2026-08-27 and 2026-08-29
// this repo's crons stopped firing entirely — no run created, nothing failed,
// nothing alerted — after 210 consecutive successes. Moving the schedule off the
// top of the hour (02:00 -> 02:07) changed nothing, so the cause is not slot
// contention. This function is the independent second opinion: it lives at
// Netlify, so a GitHub scheduler outage cannot take it down with it.
//
// It is a watchdog, not a second scheduler: it reads first and only acts on what
// is genuinely missing. On a normal day it does nothing at all.
//
// It runs TWICE (see netlify.toml). The tweet reads the data files committed by
// the index job, so firing both at once would publish yesterday's numbers. First
// pass repairs the index; second pass sees fresh data and releases the tweet.

const OWNER = process.env.GH_OWNER || 'applenostalgeek-sketch';
const REPO = process.env.GH_REPO || 'gold-fear-greed-index';
const INDEX_WORKFLOW = 'update-index.yml';
const TWEET_WORKFLOW = 'post-tweet.yml';
const ASSETS = ['gold', 'stocks', 'bonds', 'crypto'];

const todayUTC = () => new Date().toISOString().slice(0, 10);

const ghHeaders = (token) => ({
  Authorization: `Bearer ${token}`,
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
});

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

// Any run today counts, whatever its outcome. A failed run is a different problem
// and re-dispatching it on a loop would only turn one failure into many.
async function ranToday(workflow, token) {
  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/runs?per_page=10`,
    { headers: ghHeaders(token) }
  );
  if (!res.ok) throw new Error(`runs ${workflow}: HTTP ${res.status}`);
  const body = await res.json();
  const today = todayUTC();
  return (body.workflow_runs || []).some((r) => (r.created_at || '').slice(0, 10) === today);
}

async function triggerWorkflow(workflow, token) {
  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: 'POST',
      headers: { ...ghHeaders(token), 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main' }),
    }
  );
  // A successful dispatch returns 204 with no body.
  if (res.status !== 204) {
    throw new Error(`${workflow}: HTTP ${res.status} ${await res.text()}`);
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
      'Nothing was triggered. Worth a look.',
    ]);
    return { statusCode: 200, body: `unreadable: ${err.message}` };
  }

  const stale = ASSETS.filter((_, i) => dates[i] !== today);
  const token = process.env.GH_DISPATCH_TOKEN;

  if (!token) {
    if (stale.length) {
      await notify('OnOff watchdog: data is stale and I cannot fix it', [
        `Missing today's entry (${today}) for: <strong>${stale.join(', ')}</strong>.`,
        'GH_DISPATCH_TOKEN is not set on Netlify, so nothing could be triggered.',
      ]);
      return { statusCode: 500, body: 'stale but GH_DISPATCH_TOKEN missing' };
    }
    return { statusCode: 200, body: `ok: data fresh, no token to check the tweet` };
  }

  // --- 1. The index. Everything else depends on it being current. ---
  if (stale.length) {
    try {
      await triggerWorkflow(INDEX_WORKFLOW, token);
    } catch (err) {
      await notify('OnOff watchdog: could not trigger the index run', [
        `Missing today's entry (${today}) for: <strong>${stale.join(', ')}</strong>.`,
        `Dispatch failed: <strong>${err.message}</strong>`,
      ]);
      return { statusCode: 500, body: err.message };
    }
    await notify("OnOff watchdog: GitHub missed today's run, I started it", [
      `The scheduled run did not happen. Newest entry was ${dates[0]}, expected ${today}.`,
      `Assets missing today: <strong>${stale.join(', ')}</strong>.`,
      'The index workflow has been triggered and should publish within a few minutes.',
      'The tweet, if it is also missing, will be released on the next pass once the data is live.',
    ]);
    return { statusCode: 200, body: `index triggered: ${stale.join(',')}` };
  }

  // --- 2. The tweet. Only once today's numbers are actually published. ---
  let tweeted;
  try {
    tweeted = await ranToday(TWEET_WORKFLOW, token);
  } catch (err) {
    await notify('OnOff watchdog: could not check the tweet', [
      `Data is up to date for ${today}, but reading the tweet workflow failed:`,
      `<strong>${err.message}</strong>`,
    ]);
    return { statusCode: 500, body: err.message };
  }

  if (tweeted) {
    return { statusCode: 200, body: `ok: data fresh and tweet already ran (${today})` };
  }

  try {
    await triggerWorkflow(TWEET_WORKFLOW, token);
  } catch (err) {
    await notify('OnOff watchdog: could not trigger the tweet', [
      `No tweet went out today (${today}) and the dispatch failed:`,
      `<strong>${err.message}</strong>`,
    ]);
    return { statusCode: 500, body: err.message };
  }

  await notify('OnOff watchdog: no tweet today, I sent it', [
    `The data for ${today} is published, but the tweet workflow never ran.`,
    'It has been triggered and should post within a minute.',
  ]);
  return { statusCode: 200, body: 'tweet triggered' };
};
