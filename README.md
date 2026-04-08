# Survivor Alerts

Monitors Kalshi and Polymarket for new Survivor episode markets and notifies you via [ntfy](https://ntfy.sh/) when:

- A new "who will be eliminated" market is created
- The frontrunner (highest odds) changes on either platform

Runs every 5 minutes via GitHub Actions.

## Setup

1. **Install ntfy** on your phone and subscribe to a topic name of your choice
2. Fork or clone this repo (make it **private** to keep your topic name secret)
3. Add a repository secret:
   - `NTFY_TOPIC` — your ntfy topic name
4. Go to **Settings → Actions → General → Workflow permissions** and set to **Read and write permissions**
5. Trigger a manual run from the Actions tab to confirm everything works

## How it works

`check_markets.py` runs on a schedule and:

1. Fetches all events in Kalshi's `KXSURVIVORELIMINATION` series
2. Fetches all events tagged `survivor` on Polymarket
3. Compares against `seen.json` to find new markets
4. Checks the current frontrunner on each platform and compares to the previous run
5. Sends ntfy notifications for anything new
6. Commits updated `seen.json` back to the repo

## Files

- `check_markets.py` — main script
- `seen.json` — tracks seen market IDs and current frontrunners (auto-updated by the workflow)
- `.github/workflows/check.yml` — GitHub Actions workflow
