// Netlify Scheduled Function: the daily index run starts here.
//
// GitHub's scheduler stopped being usable as the primary trigger. The cron is set
// for 02:07 UTC; its start lag, measured per week on the "schedule" runs, went
// from 0.8 h in mid-August to 5 h in September and 7.2 h in early November 2026,
// on all three repos of the account at once. From 1 Nov it routinely arrived
// after the 09:02 watchdog, which then did the job. A workflow_dispatch, by
// contrast, starts within seconds.
//
// So the order is now: this function (primary) -> GitHub's own cron, scheduled
// 30 min later and in practice hours later (backup) -> the 09:02 watchdog, which
// checks the published site (last net). The workflow's guard makes every run
// after the first one that publishes stop in seconds, so the backups only ever
// compute something when the primary did not publish.
//
// It reads main on GitHub, not the site: the site lags a commit by a deploy, and
// the question here is only whether a run already produced today.
//
// No email. If this fails, the backup cron and the watchdog still follow, and
// the watchdog is the one that writes when the day is still missing at 09:02.
// It ALWAYS answers 200: Netlify re-invokes a failed function immediately (seen
// on 2026-09-13), and a retry storm of dispatches is exactly what not to cause.

const OWNER = process.env.GH_OWNER || 'applenostalgeek-sketch';
const REPO = process.env.GH_REPO || 'gold-fear-greed-index';
const INDEX_WORKFLOW = 'update-index.yml';
// Scheduled functions are cut at 30 s: two calls and one pause must fit.
const RETRY_DELAY_MS = 8000;

const todayUTC = () => new Date().toISOString().slice(0, 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const done = (body) => {
  console.log(body);
  return { statusCode: 200, body };
};

const ghHeaders = (token) => ({
  Authorization: `Bearer ${token}`,
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
});

// Newest gold date on main. Gold is what the workflow guard reads too.
async function latestOnMain(token) {
  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/contents/data/gold-fear-greed.json?ref=main`,
    { headers: { ...ghHeaders(token), Accept: 'application/vnd.github.raw+json' } }
  );
  if (!res.ok) throw new Error(`GitHub gold: HTTP ${res.status}`);
  const history = ((await res.json()) || {}).history || [];
  if (!history.length) throw new Error('gold: empty history');
  return history.reduce((max, e) => (e.date > max ? e.date : max), history[0].date);
}

async function dispatch(token) {
  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${INDEX_WORKFLOW}/dispatches`,
    {
      method: 'POST',
      headers: { ...ghHeaders(token), 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main' }),
    }
  );
  // A successful dispatch returns 204 with no body.
  if (res.status !== 204) throw new Error(`HTTP ${res.status} ${await res.text()}`);
}

async function run() {
  const token = process.env.GH_DISPATCH_TOKEN;
  if (!token) return done('GH_DISPATCH_TOKEN missing — left to the backup cron and the watchdog');

  const today = todayUTC();
  try {
    const latest = await latestOnMain(token);
    if (latest === today) return done(`ok: ${today} already on main, nothing to start`);
  } catch (err) {
    // Unknown is treated as missing: if the day was in fact published, the
    // workflow guard stops the run in seconds, which costs nothing.
    console.log(`could not read main (${err.message}) — starting the run anyway`);
  }

  // One retry. On 2026-09-13 GitHub answered 500 and still created the run, so
  // the retry may make a second one; the guard and the concurrency group turn it
  // into a no-op.
  for (const attempt of [1, 2]) {
    try {
      await dispatch(token);
      return done(`index run started (${today}, attempt ${attempt})`);
    } catch (err) {
      console.log(`dispatch attempt ${attempt} failed: ${err.message}`);
      if (attempt === 1) await sleep(RETRY_DELAY_MS);
    }
  }
  return done('dispatch failed twice — left to the backup cron and the watchdog');
}

exports.handler = async () => {
  try {
    return await run();
  } catch (err) {
    console.error(`trigger-index crashed: ${err.stack || err}`);
    return { statusCode: 200, body: `crashed: ${err.message}` };
  }
};
