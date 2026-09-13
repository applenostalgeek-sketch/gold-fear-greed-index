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
//
// It ALWAYS answers 200. On 2026-09-13, during a GitHub Actions outage, a tweet
// dispatch came back HTTP 500 and the function passed that 500 on. Netlify ran
// it again, twice, back to back within 12 seconds: three invocations, three
// identical emails. On the six normal days before it, one invocation per pass.
// The outcome goes to the log and the email, never to the status code.

const OWNER = process.env.GH_OWNER || 'applenostalgeek-sketch';
const REPO = process.env.GH_REPO || 'gold-fear-greed-index';
const SITE = process.env.SITE_URL || 'https://onoff.markets';
const INDEX_WORKFLOW = 'update-index.yml';
const TWEET_WORKFLOW = 'post-tweet.yml';
const ASSETS = ['gold', 'stocks', 'bonds', 'crypto'];

const todayUTC = () => new Date().toISOString().slice(0, 10);

// The passes fire at :02 and :27 UTC. On 2026-09-13 GitHub answered 500 to the
// tweet dispatch and still created the run 13 seconds after the last attempt,
// so a tweet failure seen on the first pass may not be one. The first pass keeps
// quiet about it; the second sees what really exists and is the one that writes.
const isSecondPass = () => new Date().getUTCMinutes() >= 15;

const done = (body) => {
  console.log(body);
  return { statusCode: 200, body };
};

const ghHeaders = (token) => ({
  Authorization: `Bearer ${token}`,
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
});

// Cache-busted: /data/* is served with a 5-minute Cache-Control, which is exactly
// the window we must not trust.
async function readPublished(file) {
  const res = await fetch(`${SITE}/data/${file}?t=${Date.now()}`, {
    headers: { 'Cache-Control': 'no-cache' },
  });
  if (!res.ok) throw new Error(`${file}: HTTP ${res.status}`);
  return res.json();
}

// Read the newest date published for one asset.
async function latestDate(asset) {
  const body = await readPublished(`${asset}-fear-greed.json`);
  const history = body.history || [];
  if (!history.length) throw new Error(`${asset}: empty history`);
  return history.reduce((max, e) => (e.date > max ? e.date : max), history[0].date);
}

// Any run today counts, whatever its outcome — queued included. A failed run is a
// different problem and re-dispatching it on a loop would only turn one failure
// into many.
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

// Never throws: a crash here would fail the invocation and get it retried.
async function notify(subject, lines) {
  const key = process.env.RESEND_API_KEY;
  const to = process.env.WATCHDOG_EMAIL;
  if (!key || !to) return; // notification is optional, never blocks the fix
  try {
    const res = await fetch('https://api.resend.com/emails', {
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
    if (!res.ok) console.error(`notify "${subject}": Resend HTTP ${res.status}`);
  } catch (err) {
    console.error(`notify "${subject}": ${err.message}`);
  }
}

async function check() {
  const today = todayUTC();
  const second = isSecondPass();
  const pass = second ? 'second pass' : 'first pass';

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
    return done(`unreadable: ${err.message}`);
  }

  const stale = ASSETS.filter((_, i) => dates[i] !== today);
  const token = process.env.GH_DISPATCH_TOKEN;

  if (!token) {
    if (stale.length) {
      await notify('OnOff watchdog: data is stale and I cannot fix it', [
        `Missing today's entry (${today}) for: <strong>${stale.join(', ')}</strong>.`,
        'GH_DISPATCH_TOKEN is not set on Netlify, so nothing could be triggered.',
      ]);
      return done('stale but GH_DISPATCH_TOKEN missing');
    }
    return done('ok: data fresh, no token to check the tweet');
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
      return done(`index dispatch failed: ${err.message}`);
    }
    await notify("OnOff watchdog: GitHub missed today's run, I started it", [
      `The scheduled run did not happen. Newest entry was ${dates[0]}, expected ${today}.`,
      `Assets missing today: <strong>${stale.join(', ')}</strong>.`,
      'The index workflow has been triggered and should publish within a few minutes.',
      'The tweet, if it is also missing, will be released on the next pass once the data is live.',
    ]);
    return done(`index triggered: ${stale.join(',')}`);
  }

  // --- 2. The tweet. Only once today's numbers are actually published. ---

  // Nothing to say today? generate_summary.py keeps the previous text when a
  // closed session barely moved, and post_tweet.py then posts nothing. Starting
  // the tweet run would only produce a run that skips — and, on 2026-09-13, three
  // emails about it. A missing or unreadable file changes nothing: check as usual.
  try {
    const summary = await readPublished('market-summary.json');
    if (summary.date === today && summary.is_new === false) {
      return done(`ok: data fresh, context reused from session ${summary.session} — no tweet due`);
    }
  } catch (err) {
    console.log(`market-summary.json unreadable (${err.message}) — checking the tweet as usual`);
  }

  let tweeted;
  try {
    tweeted = await ranToday(TWEET_WORKFLOW, token);
  } catch (err) {
    if (second) {
      await notify('OnOff watchdog: could not check the tweet', [
        `Data is up to date for ${today}, but reading the tweet workflow failed:`,
        `<strong>${err.message}</strong>`,
      ]);
    }
    return done(`tweet check failed (${pass}): ${err.message}`);
  }

  if (tweeted) {
    return done(`ok: data fresh and tweet already ran (${today})`);
  }

  try {
    await triggerWorkflow(TWEET_WORKFLOW, token);
  } catch (err) {
    if (second) {
      await notify('OnOff watchdog: could not trigger the tweet', [
        `No tweet run exists today (${today}) and the dispatch failed:`,
        `<strong>${err.message}</strong>`,
        'GitHub sometimes creates the run despite the error (it did on 2026-09-13): check the Actions tab before retrying by hand.',
      ]);
    }
    return done(`tweet dispatch failed (${pass}): ${err.message}`);
  }

  await notify('OnOff watchdog: the tweet had not run, I started it', [
    `The data for ${today} is published, but no tweet run existed yet.`,
    'The tweet workflow has been started. It still decides for itself whether there is anything worth posting.',
  ]);
  return done(`tweet triggered (${pass})`);
}

exports.handler = async () => {
  try {
    return await check();
  } catch (err) {
    // Still 200: a retry would repeat whatever this invocation already did.
    console.error(`watchdog crashed: ${err.stack || err}`);
    return { statusCode: 200, body: `crashed: ${err.message}` };
  }
};
