"""
Liveheats University Leaderboard
=================================
Fetches all heat results for a Liveheats event, extracts each surfer's
best wave per heat, joins to a university mapping, and outputs:
  - docs/leaderboard.json  : consumed by the live HTML page
  - docs/best_waves.csv    : full per-heat detail

Edit CONFIG below before pushing to GitHub.
"""

import json
import csv
import time
import os
from collections import defaultdict
from typing import Optional
import urllib.request
import urllib.error
from datetime import datetime, timezone


# ── CONFIG ────────────────────────────────────────────────────────────────────

EVENT_ID = "509040"

# If the event is private, set env var LIVEHEATS_TOKEN or paste token here.
BEARER_TOKEN: Optional[str] = os.environ.get("LIVEHEATS_TOKEN") or None

GRAPHQL_ENDPOINT = "https://liveheats.com/api/graphql"
REQUEST_DELAY = 0.3   # seconds between API calls


# ── GRAPHQL ───────────────────────────────────────────────────────────────────

def graphql(query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
    req = urllib.request.Request(GRAPHQL_ENDPOINT, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


QUERY_EVENT = """
query GetEvent($id: ID!) {
  event(id: $id) {
    id
    name
    eventDivisions {
      id
      division { name }
      heats {
        id
        round
        roundPosition
        position
        startTime
        endTime
      }
    }
  }
}
"""

QUERY_HEAT = """
query GetHeat($id: ID!) {
  heat(id: $id) {
    id
    round
    roundPosition
    startTime
    endTime
    result {
      place
      total
      rides
      competitor {
        athlete { id name }
        team { name }
      }
    }
  }
}
"""


# ── SCORE EXTRACTION ──────────────────────────────────────────────────────────

def scores_from_rides(rides) -> list[float]:
    """Return all individual wave scores from the Liveheats `rides` field, sorted descending.

    Structure: {competitor_id: [{modified_total: float, total: float, ...}, ...]}
    """
    if not isinstance(rides, dict):
        return []
    scores = []
    for ride_list in rides.values():
        if not isinstance(ride_list, list):
            continue
        for ride in ride_list:
            if not isinstance(ride, dict):
                continue
            score = ride.get("modified_total") or ride.get("total")
            if isinstance(score, (int, float)) and score > 0:
                scores.append(round(score, 4))
    scores.sort(reverse=True)
    return scores


def best_wave_from_rides(rides) -> Optional[float]:
    scores = scores_from_rides(rides)
    return scores[0] if scores else None


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Fetching event {EVENT_ID} …")
    event_data = graphql(QUERY_EVENT, {"id": EVENT_ID})
    event = event_data["event"]
    print(f"  Event: {event['name']}")

    rows = []
    uni_best_waves: dict[str, list[float]] = defaultdict(list)
    heat_details = []  # for JSON output

    EXCLUDED_DIVISIONS = {"Aloha Cup"}

    for div in event["eventDivisions"]:
        div_name = div["division"]["name"]
        if div_name in EXCLUDED_DIVISIONS:
            print(f"\n  Division '{div_name}' — skipped")
            continue
        print(f"\n  Division '{div_name}' — {len(div['heats'])} heat(s)")

        for heat_stub in div["heats"]:
            heat_id = heat_stub["id"]
            heat_label = f"{heat_stub.get('round','?')} H{(heat_stub.get('roundPosition') or heat_stub.get('position', 0)) + 1}"

            time.sleep(REQUEST_DELAY)
            heat = graphql(QUERY_HEAT, {"id": heat_id})["heat"]

            results = heat.get("result") or []
            if not results:
                print(f"    {heat_label}: no results yet, skipping")
                continue

            print(f"    {heat_label}: {len(results)} competitor(s)")

            heat_surfers = []
            for r in results:
                competitor = r.get("competitor")
                if not competitor or not competitor.get("athlete"):
                    continue
                name = competitor["athlete"]["name"]
                all_scores = scores_from_rides(r.get("rides"))
                bw = all_scores[0] if all_scores else None
                top2 = all_scores[:2]
                team = competitor.get("team")
                uni = team["name"] if team and team.get("name") else "UNKNOWN"

                rows.append({
                    "division": div_name,
                    "heat": heat_label,
                    "athlete": name,
                    "university": uni,
                    "best_wave": bw,
                    "place": r.get("place"),
                    "raw_scores": json.dumps(r.get("rides")),
                })

                if bw is not None and uni != "UNKNOWN":
                    uni_best_waves[uni].append(bw)

                heat_surfers.append({
                    "athlete": name,
                    "university": uni,
                    "best_wave": bw,
                    "top_waves": top2,
                    "place": r.get("place"),
                })

            heat_details.append({
                "division": div_name,
                "heat": heat_label,
                "surfers": heat_surfers,
            })

    # ── Leaderboard ───────────────────────────────────────────────────────────
    leaderboard = []
    for uni, waves in uni_best_waves.items():
        leaderboard.append({
            "rank": 0,
            "university": uni,
            "num_heats": len(waves),
            "mean_best_wave": round(sum(waves) / len(waves), 4),
            "max_best_wave": round(max(waves), 4),
            "min_best_wave": round(min(waves), 4),
        })
    leaderboard.sort(key=lambda x: x["mean_best_wave"], reverse=True)
    for i, row in enumerate(leaderboard, 1):
        row["rank"] = i

    # ── Write docs/leaderboard.json ───────────────────────────────────────────
    os.makedirs("docs", exist_ok=True)
    out = {
        "event_name": event["name"],
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "leaderboard": leaderboard,
        "heats": heat_details,
    }
    with open("docs/leaderboard.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote docs/leaderboard.json")

    # ── Write docs/best_waves.csv ─────────────────────────────────────────────
    with open("docs/best_waves.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["division", "heat", "athlete", "university", "best_wave", "place", "raw_scores"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote docs/best_waves.csv ({len(rows)} rows)")

    # ── Warn about athletes without a team on Liveheats ──────────────────────
    unknown = sorted({r["athlete"] for r in rows if r["university"] == "UNKNOWN"})
    if unknown:
        print(f"\n[!] {len(unknown)} athlete(s) have no team registered on Liveheats:")
        for name in unknown:
            print(f"    {name}")


if __name__ == "__main__":
    main()
