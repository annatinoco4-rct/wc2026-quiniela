"""
wc2026_quiniela.conditions
--------------------------
Real-time environmental conditions for WC 2026 venues, sourced from the
OpenWeatherMap API, converted into Elo adjustments for model.py.

Adjustments covered
~~~~~~~~~~~~~~~~~~~
- Altitude   : penalises UEFA / CAF / AFC teams at high-altitude venues
- Temperature: penalises UEFA teams in heat and warm-climate teams in cold
- AQI        : experimental penalty for poor air quality (see notes below)

Usage
~~~~~
    from conditions import get_conditions, elo_adjustments
    from model import analyse_match

    cond = get_conditions("Ciudad de México")
    adj  = elo_adjustments(cond, home_conf="CONCACAF", away_conf="UEFA")
    # Pass adj to analyse_match via cards_penalty or apply externally.
"""

import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenWeatherMap API key
# ---------------------------------------------------------------------------

OWM_API_KEY = "65c9af7632dd45b95f8eb6df198b65f6"

# ---------------------------------------------------------------------------
# Venue coordinates (static — updated only when host cities change)
# ---------------------------------------------------------------------------

VENUES: dict[str, dict] = {
    "Ciudad de México": {
        "lat": 19.4326, "lon": -99.1332, "altitude": 2240,
        "confederation_home": ["CONCACAF", "CONMEBOL"],
    },
    "Guadalajara": {
        "lat": 20.6597, "lon": -103.3496, "altitude": 1566,
        "confederation_home": ["CONCACAF", "CONMEBOL"],
    },
    "Monterrey":     {"lat": 25.6866, "lon": -100.3161, "altitude": 538},
    "Dallas":        {"lat": 32.7767, "lon": -96.7970,  "altitude": 183},
    "Los Ángeles":   {"lat": 34.0522, "lon": -118.2437, "altitude": 93},
    "San Francisco": {"lat": 37.7749, "lon": -122.4194, "altitude": 16},
    "Nueva York":    {"lat": 40.7128, "lon": -74.0060,  "altitude": 10},
    "Boston":        {"lat": 42.3601, "lon": -71.0589,  "altitude": 9},
    "Miami":         {"lat": 25.7617, "lon": -80.1918,  "altitude": 2},
    "Seattle":       {"lat": 47.6062, "lon": -122.3321, "altitude": 52},
    "Kansas City":   {"lat": 39.0997, "lon": -94.5786,  "altitude": 265},
    "Atlanta":       {"lat": 33.7490, "lon": -84.3880,  "altitude": 320},
    "Toronto":       {"lat": 43.6532, "lon": -79.3832,  "altitude": 76},
    "Vancouver":     {"lat": 49.2827, "lon": -123.1207, "altitude": 70},
}

# ---------------------------------------------------------------------------
# In-memory cache  (venue → {"data": dict, "fetched_at": float})
# ---------------------------------------------------------------------------

_cache: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _is_cached(venue: str) -> bool:
    """Return True if a fresh (< 1 h old) cache entry exists for *venue*."""
    entry = _cache.get(venue)
    if entry is None:
        return False
    return (time.time() - entry["fetched_at"]) < _CACHE_TTL_SECONDS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_conditions(venue: str) -> dict:
    """
    Fetch real-time environmental conditions for a WC 2026 host city.

    Calls two OpenWeatherMap endpoints:
        - ``/data/2.5/weather``       → current temperature (°C)
        - ``/data/2.5/air_pollution`` → Air Quality Index (1–5)

    Results are cached in memory for 1 hour to avoid hammering the API.
    On any network or API error the function logs a warning and returns
    safe defaults (temp=22, aqi=1) so the model can still run.

    Parameters
    ----------
    venue : str
        One of the keys in ``VENUES`` (e.g. ``"Ciudad de México"``).

    Returns
    -------
    dict
        ``{"venue": str, "temp_c": float, "aqi": int, "altitude": int}``

    Raises
    ------
    ValueError
        If *venue* is not in the ``VENUES`` dictionary.
    """
    if venue not in VENUES:
        raise ValueError(
            f"Unknown venue '{venue}'. Valid venues: {list(VENUES.keys())}"
        )

    if _is_cached(venue):
        logger.debug("Cache hit for %s", venue)
        return _cache[venue]["data"]

    info = VENUES[venue]
    lat, lon = info["lat"], info["lon"]

    # --- Fetch temperature ---------------------------------------------------
    temp_c: float = 22.0  # safe default
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric"},
            timeout=8,
        )
        resp.raise_for_status()
        temp_c = resp.json()["main"]["temp"]
    except Exception as exc:  # network error, bad JSON, key missing, etc.
        logger.warning(
            "Could not fetch temperature for %s (%s). Using default 22°C.", venue, exc
        )

    # --- Fetch AQI -----------------------------------------------------------
    aqi: int = 1  # safe default (best air quality)
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/air_pollution",
            params={"lat": lat, "lon": lon, "appid": OWM_API_KEY},
            timeout=8,
        )
        resp.raise_for_status()
        aqi = resp.json()["list"][0]["main"]["aqi"]
    except Exception as exc:
        logger.warning(
            "Could not fetch AQI for %s (%s). Using default AQI=1.", venue, exc
        )

    result: dict = {
        "venue":    venue,
        "temp_c":   round(float(temp_c), 1),
        "aqi":      int(aqi),
        "altitude": info["altitude"],
    }

    # Store in cache
    _cache[venue] = {"data": result, "fetched_at": time.time()}
    logger.info("Fetched conditions for %s: %s", venue, result)
    return result


def elo_adjustments(
    conditions: dict,
    home_conf: str,
    away_conf: str,
) -> dict:
    """
    Convert environmental conditions into signed Elo adjustments.

    All adjustments are *penalties* (negative Elo deltas) applied to the
    team that is disadvantaged by the conditions.

    Altitude rules
    ~~~~~~~~~~~~~~
    - Venue > 1500 m and team is UEFA / CAF / AFC → –60 Elo
    - Venue 1000–1500 m and team is UEFA / CAF / AFC → –30 Elo
    - CONCACAF / CONMEBOL teams → no altitude penalty

    Temperature rules
    ~~~~~~~~~~~~~~~~~
    - Temp > 28°C and team is UEFA → –30 Elo
    - Temp < 18°C and team is CAF  → –20 Elo

    AQI rules  *(experimental — no empirical validation; included for
    exploratory purposes only.  Weight may be reduced to 0 in production.)*
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    - AQI 4 → –8 Elo applied to **both** teams
    - AQI 5 → –15 Elo applied to **both** teams
    - AQI 1–3 → no effect

    Parameters
    ----------
    conditions : dict
        Output of ``get_conditions()``.
    home_conf : str
        Confederation of the home team (e.g. ``"UEFA"``, ``"CAF"``).
    away_conf : str
        Confederation of the away team.

    Returns
    -------
    dict
        ``{"home_adjustment": int, "away_adjustment": int}``
        Negative values mean the team is penalised.
    """
    alt   = conditions["altitude"]
    temp  = conditions["temp_c"]
    aqi   = conditions["aqi"]

    penalised_at_altitude = {"UEFA", "CAF", "AFC"}

    home_adj = 0
    away_adj = 0

    # --- Altitude --------------------------------------------------------------
    if alt > 1500:
        if home_conf in penalised_at_altitude:
            home_adj -= 60
        if away_conf in penalised_at_altitude:
            away_adj -= 60
    elif alt >= 1000:
        if home_conf in penalised_at_altitude:
            home_adj -= 30
        if away_conf in penalised_at_altitude:
            away_adj -= 30

    # --- Temperature ----------------------------------------------------------
    if temp > 28:
        if home_conf == "UEFA":
            home_adj -= 30
        if away_conf == "UEFA":
            away_adj -= 30
    elif temp < 18:
        if home_conf == "CAF":
            home_adj -= 20
        if away_conf == "CAF":
            away_adj -= 20

    # --- AQI (experimental) ---------------------------------------------------
    # NOTE: The relationship between air quality index and athletic performance
    # in 90-minute football matches is not empirically validated.  Treat these
    # values as exploratory placeholders subject to revision.
    if aqi == 4:
        home_adj -= 8
        away_adj -= 8
    elif aqi >= 5:
        home_adj -= 15
        away_adj -= 15

    return {"home_adjustment": home_adj, "away_adjustment": away_adj}


# ---------------------------------------------------------------------------
# Integration helper — wraps analyse_match with live conditions
# ---------------------------------------------------------------------------

def analyse_match_with_conditions(
    home:           str,
    away:           str,
    venue:          str,
    home_conf:      str,
    away_conf:      str,
    is_host:        bool = False,
    travel_fatigue: Optional[dict] = None,
) -> dict:
    """
    Convenience wrapper: fetch live conditions, compute Elo adjustments,
    and run the full match analysis.

    Parameters
    ----------
    home, away : str
        Team names (keys in model.ELO_RATINGS).
    venue : str
        Host city (key in VENUES).
    home_conf, away_conf : str
        Confederation strings for climate/altitude logic.
    is_host : bool
        Whether the home team is a 2026 host nation.
    travel_fatigue : dict, optional
        Passed directly to ``model.analyse_match()``.

    Returns
    -------
    dict
        Output of ``model.analyse_match()`` extended with a ``"conditions"`` key
        containing the raw environmental data and computed Elo adjustments.
        Falls back to standard ``analyse_match()`` if condition fetch fails.
    """
    # Import here to avoid circular dependency if conditions.py is imported
    # at module level in model.py in the future.
    from model import analyse_match, ELO_RATINGS

    try:
        cond = get_conditions(venue)
        adj  = elo_adjustments(cond, home_conf, away_conf)
    except Exception as exc:
        logger.warning(
            "Conditions fetch failed for %s (%s). Running without adjustments.", venue, exc
        )
        result = analyse_match(home, away, is_host, venue, travel_fatigue)
        result["conditions"] = None
        return result

    # Apply adjustments via cards_penalty (Elo subtraction mechanism)
    # Negate because cards_penalty convention is positive = subtract
    cards = {
        "home": -adj["home_adjustment"],  # e.g. -(-60) = 60 pts subtracted
        "away": -adj["away_adjustment"],
    }
    # Remove zeros to keep it clean
    cards = {k: v for k, v in cards.items() if v != 0}

    result = analyse_match(
        home,
        away,
        is_host,
        venue          = venue,
        travel_fatigue = travel_fatigue,
    )

    # Patch Elo into result metadata (cards_penalty is applied inside three_way_probs
    # — here we document what was applied)
    result["conditions"] = {
        "raw": cond,
        "elo_adjustments": adj,
    }
    return result


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("\n" + "=" * 55)
    print("  Live conditions — Ciudad de México")
    print("=" * 55)

    try:
        cond = get_conditions("Ciudad de México")
        print(f"  Venue    : {cond['venue']}")
        print(f"  Temp     : {cond['temp_c']} °C")
        print(f"  AQI      : {cond['aqi']}  (1=good, 5=very poor)")
        print(f"  Altitude : {cond['altitude']} m")

        adj_home_uefa = elo_adjustments(cond, home_conf="CONCACAF", away_conf="UEFA")
        print(f"\n  Elo adjustments (CONCACAF home vs UEFA away):")
        print(f"    home_adjustment : {adj_home_uefa['home_adjustment']:+d} Elo")
        print(f"    away_adjustment : {adj_home_uefa['away_adjustment']:+d} Elo")

    except Exception as e:
        print(f"  ERROR: {e}")

    print()
