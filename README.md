# ADH Open – Uni Leaderboard

Live university leaderboard for the ADH Open Wellenreiten, powered by the [Liveheats](https://liveheats.com) API.

GitHub Actions fetches heat results every 5 minutes and publishes a ranked leaderboard to GitHub Pages.

**Live site:** [lennartredl.github.io/UniLeaderboard](https://lennartredl.github.io/UniLeaderboard/)

---

## How it works

1. `fetch_leaderboard.py` queries the Liveheats GraphQL API for all heats in the configured event
2. For each completed heat, it extracts each surfer's best individual wave score from the `rides` field
3. University names are read directly from each competitor's registered team on Liveheats — no manual mapping needed
4. Universities are ranked by **mean best wave** across all heats in the Open and Longboard divisions (Aloha Cup excluded)
5. Results are written to `docs/leaderboard.json`, which the live page polls every 5 minutes

## Configuration

To use this for a different event, edit one line in `fetch_leaderboard.py`:

```python
EVENT_ID = "509040"   # ← your Liveheats event ID
```

The event ID is in the Liveheats URL: `liveheats.com/events/509040`.

### Private events

If the event is private, add a `LIVEHEATS_TOKEN` secret in repo **Settings → Secrets → Actions**.

### Excluded divisions

To exclude a division from the ranking (e.g. Aloha Cup):

```python
EXCLUDED_DIVISIONS = {"Aloha Cup"}
```

---

## GitHub Pages setup

- Repo **Settings → Pages → Deploy from branch → main / /docs**
- Live at `https://YOUR_USERNAME.github.io/YOUR_REPO/`

---

## Files

```
fetch_leaderboard.py              ← data fetcher (only config needed: EVENT_ID)
.github/workflows/
  update_leaderboard.yml          ← runs every 5 min via GitHub Actions
docs/
  index.html                      ← live leaderboard page
  leaderboard.json                ← updated automatically on each run
  best_waves.csv                  ← full per-heat detail
  adh-logo.png                    ← event logo
```

## Stopping after the event

Disable the workflow: **Actions → Update Leaderboard → ⋯ → Disable workflow**
