"""
wc2026_quiniela.data
--------------------
Fetches live World Cup 2026 data from football-data.org and persists it as CSV.

Environment variable required:
    FOOTBALL_DATA_KEY  — your API key from https://www.football-data.org/

Rate limit: 1 request/second (free tier allows 10 req/min).
"""

import csv
import os
import time
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = "https://api.football-data.org/v4"
WC_CODE = "WC"
DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_CSV = DATA_DIR / "results.csv"
CARDS_CSV = DATA_DIR / "cards.csv"

RESULTS_FIELDS = ["date", "home", "away", "home_goals", "away_goals", "group", "round"]
CARDS_FIELDS = ["date", "match_id", "team", "player", "card_type", "minute"]

_RATE_LIMIT_SECS = 1.0  # free tier: 10 req/min


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _session() -> requests.Session:
    key = os.environ.get("FOOTBALL_DATA_KEY")
    if not key:
        raise EnvironmentError("FOOTBALL_DATA_KEY environment variable is not set.")
    s = requests.Session()
    s.headers.update({"X-Auth-Token": key})
    return s


def _get(session: requests.Session, path: str, **params) -> Any:
    url = f"{API_BASE}/{path}"
    response = session.get(url, params=params, timeout=15)
    response.raise_for_status()
    time.sleep(_RATE_LIMIT_SECS)
    return response.json()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_results() -> int:
    """
    Pull all WC 2026 match results and write them to data/results.csv.

    Returns the number of finished matches written.
    """
    session = _session()
    data = _get(session, f"competitions/{WC_CODE}/matches")
    matches = data.get("matches", [])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = 0

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_FIELDS)
        writer.writeheader()

        for m in matches:
            score = m.get("score", {})
            full = score.get("fullTime", {})
            home_goals = full.get("home")
            away_goals = full.get("away")

            # Skip matches not yet played
            if home_goals is None or away_goals is None:
                continue

            stage = m.get("stage", "")
            group = m.get("group") or ""
            match_day = m.get("matchday")
            round_label = group if group else f"Round {match_day}" if match_day else stage

            writer.writerow({
                "date": m.get("utcDate", "")[:10],
                "home": m["homeTeam"]["name"],
                "away": m["awayTeam"]["name"],
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
                "group": group,
                "round": round_label,
            })
            written += 1

    return written


def fetch_cards() -> int:
    """
    Pull bookings (yellow/red cards) for every WC 2026 match and write to data/cards.csv.

    Returns the total number of card events written.
    """
    session = _session()
    data = _get(session, f"competitions/{WC_CODE}/matches")
    matches = data.get("matches", [])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = 0

    with open(CARDS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CARDS_FIELDS)
        writer.writeheader()

        for m in matches:
            if m.get("status") not in ("FINISHED", "IN_PLAY", "PAUSED"):
                continue

            match_id = m["id"]
            match_date = m.get("utcDate", "")[:10]

            # Fetch individual match detail for bookings
            try:
                detail = _get(session, f"matches/{match_id}")
            except requests.HTTPError as exc:
                print(f"  Warning: could not fetch match {match_id}: {exc}")
                continue

            bookings = detail.get("bookings", [])
            for booking in bookings:
                team_obj = booking.get("team") or {}
                player_obj = booking.get("player") or {}
                writer.writerow({
                    "date": match_date,
                    "match_id": match_id,
                    "team": team_obj.get("name", ""),
                    "player": player_obj.get("name", ""),
                    "card_type": booking.get("card", ""),
                    "minute": booking.get("minute", ""),
                })
                written += 1

    return written


def update_all() -> None:
    """Refresh results and cards CSVs and print a summary."""
    print("Fetching WC 2026 results...")
    try:
        n_matches = fetch_results()
        print(f"  {n_matches} finished matches saved to {RESULTS_CSV}")
    except Exception as exc:
        print(f"  ERROR fetching results: {exc}")
        n_matches = 0

    print("Fetching WC 2026 bookings (cards)...")
    try:
        n_cards = fetch_cards()
        print(f"  {n_cards} card events saved to {CARDS_CSV}")
    except Exception as exc:
        print(f"  ERROR fetching cards: {exc}")
        n_cards = 0

    print(f"\nDone. {n_matches} matches | {n_cards} cards.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    update_all()
