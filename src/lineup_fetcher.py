"""
wc2026_quiniela.lineup_fetcher
-------------------------------
Pulls confirmed/likely starting lineups straight from 365scores.com's
unofficial web API (no PyPI package — that one is broken/abandoned).

Endpoint (single game, per 365scores' own frontend calls):
    GET https://webws.365scores.com/web/game/?appTypeId=5&langId=31&gameId={game_id}

Fixtures endpoints (used to resolve a gameId from team names + date) — tried
in order, since /games/results/ only returns already-finished matches:
    GET https://webws.365scores.com/web/games/?appTypeId=5&langId=31
        &timezoneName=America/Mexico_City&userCountryId=-1&competitions={competition_id}
        (live + scheduled)
    GET https://webws.365scores.com/web/games/results/?appTypeId=5&langId=31
        &timezoneName=America/Mexico_City&userCountryId=-1&competitions={competition_id}
        (finished)

All of these were confirmed live against the real WC 2026 competition (id 5930)
while building this module — e.g. gameId 4748888 = México vs Ecuador, Round of
16, 2026-06-30, with `homeCompetitor.symbolicName == "MEX"`.

Key design choice: team matching uses 365scores' `symbolicName` (3-letter FIFA
code, e.g. "MEX", "ARG") instead of the localized `name` field. `langId=31`
returns Brazilian-Portuguese strings ("Equador", "Argélia", "Tchéquia"...)
which don't line up cleanly with this project's own team-name convention in
model.ELO_RATINGS (itself a mixed ES/EN convention — see TEAM_CODE_MAP below).
Matching on symbolicName sidesteps that whole translation problem.

Player names inside lineups are NOT localized (they're proper nouns), so
langId doesn't affect PLAYER_IMPACT matching.

Usage
~~~~~
    from lineup_fetcher import get_game_id, fetch_lineup, fetch_live_events, adjusted_elo

    game_id = get_game_id("México", "Sudáfrica", "2026-06-11")
    lineup  = fetch_lineup(game_id)
    elo     = adjusted_elo("México", lineup["home"], base_elo=1857.17)

    if lineup["status_group"] != 1:   # match already live or finished
        events = fetch_live_events(game_id)
"""

from __future__ import annotations

import logging
import time
import unicodedata
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://webws.365scores.com/web"
PAGE_HOST = "https://webws.365scores.com"

APP_TYPE_ID = 5
LANG_ID = 31  # Brazilian Portuguese — see module docstring on why this is fine
DEFAULT_TIMEZONE = "America/Mexico_City"

# FIFA World Cup 2026 competition id on 365scores — confirmed live via
# https://www.365scores.com/football/league/fifa-world-cup-5930
WC_COMPETITION_ID = 5930

# Fixture-search endpoints, in try-order. /games/results/ only returns finished
# matches — live and scheduled-but-not-started games live under /games/ instead.
# get_game_id() tries /games/ first (the common T-60/live case), then falls
# back to /games/results/ for matches that have already wrapped up.
GAME_ENDPOINTS = [
    f"{BASE_URL}/games/",           # live + scheduled
    f"{BASE_URL}/games/results/",   # finished
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.365scores.com/",
    "Accept": "application/json, text/plain, */*",
}

_REQUEST_TIMEOUT = 8  # seconds — lower than the usual 10s default; the fixtures
                       # endpoints were read-timing-out at 10s in practice.


class LineupFetchError(RuntimeError):
    """Raised when the 365scores API can't be reached or returns something unusable."""


# ---------------------------------------------------------------------------
# Team name -> 365scores symbolicName (FIFA 3-letter code)
# ---------------------------------------------------------------------------
# Keys must match model.ELO_RATINGS exactly. Values verified against the
# live API where possible (MEX, ECU confirmed directly); the rest follow
# the same standard FIFA/365scores code convention and should be spot-checked
# once a team's real fixtures start appearing (a code mismatch just means
# get_game_id() won't find that team's matches — it fails loudly, not silently).
TEAM_CODE_MAP: dict[str, str] = {
    "México": "MEX", "Sudáfrica": "RSA", "Corea del Sur": "KOR", "Chequia": "CZE",
    "Canadá": "CAN", "Bosnia": "BIH", "Qatar": "QAT", "Suiza": "SUI",
    "Brasil": "BRA", "Marruecos": "MAR", "Haití": "HAI", "Escocia": "SCO",
    "USA": "USA", "Paraguay": "PAR", "Australia": "AUS", "Turquía": "TUR",
    "Alemania": "GER", "Curazao": "CUW", "Países Bajos": "NED", "Japón": "JPN",
    "España": "ESP", "Cabo Verde": "CPV", "Bélgica": "BEL", "Egipto": "EGY",
    "Arabia Saudita": "KSA", "Uruguay": "URU", "Irán": "IRN", "Nueva Zelanda": "NZL",
    "Francia": "FRA", "Albania": "ALB", "Portugal": "POR", "Argentina": "ARG",
    "Inglaterra": "ENG", "Croacia": "CRO", "Ghana": "GHA", "Panamá": "PAN",
    "Colombia": "COL", "Ecuador": "ECU", "Senegal": "SEN", "Uzbekistán": "UZB",
    "Italia": "ITA", "Congo DR": "COD", "Serbia": "SRB", "Jordania": "JOR",
    "Dinamarca": "DEN", "Costa Rica": "CRC", "Iraq": "IRQ",
}


# ---------------------------------------------------------------------------
# Key-player Elo weights
# ---------------------------------------------------------------------------
# Subjective, hand-tuned starting points (in the same spirit as model.py's
# DRAW_TENDENCY / CONFEDERATION constants) — how many Elo points a team is
# estimated to lose if this player is NOT in the confirmed lineup at all.
# Recalibrate as the tournament plays out. "team" must match model.ELO_RATINGS.
PLAYER_IMPACT: dict[str, dict] = {
    "Kylian Mbappé":     {"team": "Francia",      "elo_weight": 70},
    "Lionel Messi":      {"team": "Argentina",    "elo_weight": 65},
    "Jude Bellingham":   {"team": "Inglaterra",   "elo_weight": 55},
    "Harry Kane":        {"team": "Inglaterra",   "elo_weight": 50},
    "Cristiano Ronaldo": {"team": "Portugal",     "elo_weight": 45},
    "Bruno Fernandes":   {"team": "Portugal",     "elo_weight": 40},
    "Vinícius Júnior":   {"team": "Brasil",       "elo_weight": 55},
    "Rodrygo":           {"team": "Brasil",       "elo_weight": 35},
    "Pedri":             {"team": "España",       "elo_weight": 45},
    "Lamine Yamal":      {"team": "España",       "elo_weight": 55},
    "Kevin De Bruyne":   {"team": "Bélgica",      "elo_weight": 50},
    "Virgil van Dijk":   {"team": "Países Bajos", "elo_weight": 45},
    "Cody Gakpo":        {"team": "Países Bajos", "elo_weight": 30},
    "Jamal Musiala":     {"team": "Alemania",     "elo_weight": 50},
    "Florian Wirtz":     {"team": "Alemania",     "elo_weight": 45},
    "James Rodríguez":   {"team": "Colombia",     "elo_weight": 40},
    "Luis Díaz":         {"team": "Colombia",     "elo_weight": 35},
    "Achraf Hakimi":     {"team": "Marruecos",    "elo_weight": 35},
    "Federico Valverde": {"team": "Uruguay",      "elo_weight": 40},
    "Darwin Núñez":      {"team": "Uruguay",      "elo_weight": 30},
    "Christian Pulisic":  {"team": "USA",         "elo_weight": 35},
    "Edson Álvarez":     {"team": "México",       "elo_weight": 30},
    "Santiago Giménez":  {"team": "México",       "elo_weight": 35},
    "Luka Modrić":       {"team": "Croacia",      "elo_weight": 40},
}


# ---------------------------------------------------------------------------
# In-memory caches (short TTL — lineup confirmations and live events flip
# right up to and during kickoff, so we don't want stale data cached long)
# ---------------------------------------------------------------------------

_lineup_cache: dict[int, dict] = {}
_game_payload_cache: dict[int, dict] = {}
_CACHE_TTL_SECONDS = 60


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _get(url: str, params: Optional[dict] = None) -> dict:
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise LineupFetchError(f"365scores request failed for {url}: {exc}") from exc
    except ValueError as exc:  # bad JSON
        raise LineupFetchError(f"365scores returned non-JSON for {url}: {exc}") from exc


def _fetch_game_payload(game_id: int, use_cache: bool = True) -> dict:
    """
    Fetch (and cache) the raw `game` object from /web/game/ for *game_id*.

    Shared by fetch_lineup() and fetch_live_events() so a single call covers
    both — this endpoint returns lineups, events, and the members directory
    all in one response, no reason to hit it twice within the TTL window.
    """
    now = time.time()
    if use_cache:
        cached = _game_payload_cache.get(game_id)
        if cached and (now - cached["fetched_at"]) < _CACHE_TTL_SECONDS:
            logger.debug("Game payload cache hit for gameId=%s", game_id)
            return cached["data"]

    payload = _get(f"{BASE_URL}/game/", {
        "appTypeId": APP_TYPE_ID,
        "langId": LANG_ID,
        "gameId": game_id,
    })
    game = payload.get("game")
    if not game:
        raise LineupFetchError(f"No 'game' key in 365scores response for gameId={game_id}")

    _game_payload_cache[game_id] = {"data": game, "fetched_at": now}
    return game


# ---------------------------------------------------------------------------
# fetch_lineup
# ---------------------------------------------------------------------------

def fetch_lineup(
    game_id: Optional[int] = None,
    use_cache: bool = True,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    date: Optional[str] = None,
) -> dict:
    """
    Fetch the confirmed (or projected) lineup for a single 365scores game.

    Parameters
    ----------
    game_id : int, optional
        365scores gameId. If provided, used directly — skips the
        get_game_id() fixture search entirely.
    use_cache : bool
        Reuse an in-memory result younger than _CACHE_TTL_SECONDS.
    home_team, away_team, date : str, optional
        Only used when *game_id* is None: forwarded to get_game_id() to
        resolve it first. Ignored (with the search skipped) if game_id
        is given directly.

    Returns
    -------
    dict
        {
          "home": [{"name": str, "position": str, "status": "starting"|"substitute"}, ...],
          "away": [...],
          "confirmed": bool,        # game["hasLineups"] — both lineups are out
          "home_confirmed": bool,   # homeCompetitor.lineups.status == "Confirmado"
          "away_confirmed": bool,   # awayCompetitor.lineups.status == "Confirmado"
          "status_group": int,     # game["statusGroup"] (1 = not started yet)
          "status_text": str,      # game["statusText"], e.g. "Fim" (finished)
        }
        Coaching staff (status 4 in the API) are filtered out.

    Raises
    ------
    ValueError
        If game_id is None and home_team/away_team/date weren't all provided
        either (nothing to resolve or fetch).
    LineupFetchError
        On network/HTTP failure or an unparseable response.
    """
    if game_id is None:
        if not (home_team and away_team and date):
            raise ValueError(
                "fetch_lineup() necesita game_id, o home_team + away_team + date para resolverlo."
            )
        game_id = get_game_id(home_team, away_team, date)

    now = time.time()
    if use_cache:
        cached = _lineup_cache.get(game_id)
        if cached and (now - cached["fetched_at"]) < _CACHE_TTL_SECONDS:
            logger.debug("Lineup cache hit for gameId=%s", game_id)
            return cached["data"]

    game = _fetch_game_payload(game_id, use_cache=use_cache)

    # Player id -> display name directory (lineups.members only carries stats/position,
    # not the name itself — confirmed against a live fetch of this endpoint).
    name_by_id = {
        m["id"]: m.get("name", f"Player#{m['id']}")
        for m in game.get("members", [])
        if "id" in m
    }

    result: dict = {
        "home": [], "away": [],
        "confirmed": bool(game.get("hasLineups", False)),
        "home_confirmed": False, "away_confirmed": False,
        "status_group": game.get("statusGroup"),
        "status_text": game.get("statusText", ""),
    }

    for side in ("home", "away"):
        competitor = game.get(f"{side}Competitor") or {}
        lineups = competitor.get("lineups") or {}
        result[f"{side}_confirmed"] = lineups.get("status") == "Confirmado"

        for member in lineups.get("members", []):
            status = member.get("status")
            if status == 4:  # management/coaching staff — not a player
                continue
            player_id = member.get("id")
            position = (member.get("position") or {}).get("shortName", "")
            result[side].append({
                "name": name_by_id.get(player_id, f"Player#{player_id}"),
                "position": position,
                "status": "starting" if status == 1 else "substitute",
            })

    _lineup_cache[game_id] = {"data": result, "fetched_at": now}
    return result


# ---------------------------------------------------------------------------
# fetch_live_events
# ---------------------------------------------------------------------------

def fetch_live_events(game_id: int, use_cache: bool = True) -> list[dict]:
    """
    Fetch the live event feed (goals, cards, substitutions) for a game.

    Reads game["events"], each raw event expected to look like::

        {"gameTime": <minute>, "eventType": {"name": <str>}, "competitorId": <int>, "playerId": <int>}

    NOTE: the "events" key/shape is the one place in this module that
    couldn't be confirmed against a live payload while building it (the
    single-game response for an in-progress/finished match is large enough
    that our fetch tooling truncated before reaching it — lineups + per-player
    stats alone run past 80k characters). If 365scores names or nests this
    differently, this is the first place to check — everything downstream
    (gameday.py's live section) degrades gracefully to "no events" rather
    than crashing.

    Parameters
    ----------
    game_id : int
    use_cache : bool
        Reuse the cached raw game payload (shared with fetch_lineup) if fresh.

    Returns
    -------
    list of dict, sorted by minute ascending, each::
        {
          "minute": float | None,
          "type": str,             # e.g. "Gol", "Cartão Amarelo", "Substitution"
          "competitor_id": int | None,
          "player_id": int | None,
          "player_name": str | None,   # resolved from game["members"], if found
          "side": "home" | "away" | None,
        }
    """
    game = _fetch_game_payload(game_id, use_cache=use_cache)

    name_by_id = {m["id"]: m.get("name") for m in game.get("members", []) if "id" in m}
    side_by_competitor_id = {}
    for side in ("home", "away"):
        cid = (game.get(f"{side}Competitor") or {}).get("id")
        if cid is not None:
            side_by_competitor_id[cid] = side

    events = []
    for e in game.get("events", []):
        raw_type = e.get("eventType")
        event_type = raw_type.get("name", "") if isinstance(raw_type, dict) else (raw_type or "")
        competitor_id = e.get("competitorId")
        player_id = e.get("playerId")
        events.append({
            "minute": e.get("gameTime"),
            "type": event_type,
            "competitor_id": competitor_id,
            "player_id": player_id,
            "player_name": name_by_id.get(player_id),
            "side": side_by_competitor_id.get(competitor_id),
        })

    events.sort(key=lambda ev: (ev["minute"] is None, ev["minute"]))
    return events


# ---------------------------------------------------------------------------
# get_game_id
# ---------------------------------------------------------------------------

def _iter_fixture_pages(direction_key: str, start_data: dict, max_pages: int):
    """Yield successive fixtures pages by following paging[direction_key]."""
    data = start_data
    seen = set()
    for _ in range(max_pages):
        next_path = (data.get("paging") or {}).get(direction_key)
        if not next_path or next_path in seen:
            return
        seen.add(next_path)
        data = _get(f"{PAGE_HOST}{next_path}")
        yield data


def get_game_id(
    home_team: str,
    away_team: str,
    date: str,
    game_id: Optional[int] = None,
    max_pages_each_direction: int = 6,
) -> int:
    """
    Resolve a 365scores gameId for a WC 2026 fixture from team names + date.

    Parameters
    ----------
    home_team, away_team : str
        Team names as used in model.ELO_RATINGS (e.g. "México", "Sudáfrica").
        Matched via TEAM_CODE_MAP -> symbolicName, not the localized API name.
    date : str
        ISO date "YYYY-MM-DD" (matches results.csv / picks convention).
    game_id : int, optional
        If provided, skip the fixture search entirely and return this id
        as-is (e.g. when you already pulled it from a 365scores match URL).
    max_pages_each_direction : int
        How many extra fixtures pages to walk forward and backward from the
        API's default window before giving up (the endpoint paginates around
        a "current" cursor, so a date far in the past/future may need paging).
        Only used as a fallback — see search strategy below.

    Search strategy
    ----------------
    1. One single-page request (no pagination) to GAME_ENDPOINTS[0] (/games/ —
       live + scheduled matches, the common case when running this near kickoff).
    2. If not found, one single-page request to GAME_ENDPOINTS[1] (/games/results/
       — finished matches).
    3. Only if neither default page has it: walk pagination (forward and
       backward) on both endpoints before giving up.

    Returns
    -------
    int
        The matching gameId.

    Raises
    ------
    ValueError
        If either team isn't in TEAM_CODE_MAP.
    LookupError
        If no matching fixture is found within the paging budget.
    """
    if game_id is not None:
        return int(game_id)

    home_code = TEAM_CODE_MAP.get(home_team)
    away_code = TEAM_CODE_MAP.get(away_team)
    if not home_code or not away_code:
        missing = [t for t, c in [(home_team, home_code), (away_team, away_code)] if not c]
        raise ValueError(
            f"Sin código FIFA para: {missing}. Agrégalo a TEAM_CODE_MAP en lineup_fetcher.py."
        )

    target_date = date[:10]

    def _search(games: list) -> Optional[int]:
        for g in games:
            if g.get("startTime", "")[:10] != target_date:
                continue
            h = (g.get("homeCompetitor") or {}).get("symbolicName")
            a = (g.get("awayCompetitor") or {}).get("symbolicName")
            if {h, a} == {home_code, away_code}:
                return int(g["id"])
        return None

    params = {
        "appTypeId": APP_TYPE_ID,
        "langId": LANG_ID,
        "timezoneName": DEFAULT_TIMEZONE,
        "userCountryId": -1,
        "competitions": WC_COMPETITION_ID,
    }

    # Fast path: one request per endpoint, no pagination. /games/ (live +
    # scheduled) first, /games/results/ (finished) second.
    first_pages: dict[str, dict] = {}
    for endpoint in GAME_ENDPOINTS:
        data = _get(endpoint, params)
        first_pages[endpoint] = data
        match = _search(data.get("games", []))
        if match:
            return match

    # Fallback: the fixture wasn't on either endpoint's default window —
    # walk pagination both directions on both endpoints before giving up.
    for endpoint, first in first_pages.items():
        for data in _iter_fixture_pages("nextPage", first, max_pages_each_direction):
            match = _search(data.get("games", []))
            if match:
                return match

        for data in _iter_fixture_pages("previousPage", first, max_pages_each_direction):
            match = _search(data.get("games", []))
            if match:
                return match

    raise LookupError(
        f"No se encontró gameId para {home_team} vs {away_team} el {date} "
        f"(competitions={WC_COMPETITION_ID}, endpoints={GAME_ENDPOINTS}, "
        f"±{max_pages_each_direction} páginas)."
    )


# ---------------------------------------------------------------------------
# adjusted_elo
# ---------------------------------------------------------------------------

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _lineup_entries(lineup: list) -> list[tuple[str, str]]:
    """Normalize a lineup (list of dicts or plain name strings) to (name, status) pairs."""
    entries = []
    for p in lineup:
        if isinstance(p, dict):
            entries.append((p.get("name", ""), p.get("status", "starting")))
        else:
            entries.append((str(p), "starting"))
    return entries


def adjusted_elo(team: str, lineup: list, base_elo: float) -> float:
    """
    Penalise a team's Elo rating for PLAYER_IMPACT players missing from *lineup*.

    - Player absent from the lineup entirely (not even on the bench) -> full
      elo_weight penalty (likely injury/suspension/rotation out of the squad).
    - Player present but status == "substitute" (benched) -> half penalty.
    - Player starting -> no penalty.

    Matching is surname-based and accent-insensitive, since API player names
    and PLAYER_IMPACT keys may not be formatted identically.

    Parameters
    ----------
    team : str
        Team name, must match a "team" value used in PLAYER_IMPACT (and ideally
        model.ELO_RATINGS).
    lineup : list
        Either fetch_lineup(...)["home"/"away"] (list of dicts with "name" and
        "status"), or a plain list of player-name strings (treated as starters).
    base_elo : float
        Elo rating before lineup adjustment.

    Returns
    -------
    float
        base_elo minus total penalty (can be negative-delta only, never a bonus).
    """
    entries = _lineup_entries(lineup)
    normalized = [(_strip_accents(name).lower(), status) for name, status in entries]

    penalty = 0.0
    for player, info in PLAYER_IMPACT.items():
        if info["team"] != team:
            continue
        surname = _strip_accents(player.split()[-1]).lower()
        status = next((s for name, s in normalized if surname in name), None)
        if status is None:
            penalty += info["elo_weight"]
        elif status == "substitute":
            penalty += info["elo_weight"] * 0.5
        # status == "starting" -> no penalty

    return base_elo - penalty


# ---------------------------------------------------------------------------
# Quick CLI / smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) >= 4:
        home, away, date = sys.argv[1], sys.argv[2], sys.argv[3]
    else:
        home, away, date = "México", "Sudáfrica", "2026-06-11"

    print(f"\nBuscando gameId para {home} vs {away} el {date}...")
    try:
        gid = get_game_id(home, away, date)
        print(f"  gameId = {gid}")
        lineup = fetch_lineup(gid)
        for side, label in (("home", home), ("away", away)):
            confirmed = "CONFIRMADA" if lineup[f"{side}_confirmed"] else "no confirmada"
            print(f"\n  {label} ({confirmed}) — {len(lineup[side])} jugadores:")
            for p in lineup[side][:11]:
                print(f"    {p['status']:<10} {p['position']:<12} {p['name']}")
        home_elo = adjusted_elo(home, lineup["home"], base_elo=1857.17)
        print(f"\n  Elo ajustado {home}: {home_elo:.1f}")

        if lineup["status_group"] != 1:
            print(f"\n  Partido en curso/finalizado ({lineup['status_text']}) — eventos:")
            for ev in fetch_live_events(gid):
                who = ev["player_name"] or ev["player_id"]
                print(f"    {ev['minute']}'  {ev['type']:<20} {who} ({ev['side']})")
    except (ValueError, LookupError, LineupFetchError) as exc:
        print(f"  ERROR: {exc}")
