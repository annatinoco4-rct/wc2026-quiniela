"""
wc2026_quiniela.model
---------------------
Core Elo + Bivariate Poisson model for World Cup 2026 match prediction.

Scoring system (Prodemaster):
    - Exact scoreline : 3 pts
    - Correct result  : 1 pt
    - Champion pick   : 6 pts
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POINTS = {"exact": 3, "result": 1, "champion": 6}

# Average goals per team per WC match (historical calibration)
LAMBDA_BASE = 1.35

# Elo boost for home/neutral advantage
ELO_BOOST_STANDARD = 60    # Standard home advantage
ELO_BOOST_HOST     = 100   # Tournament host nation (MEX / USA / CAN in 2026)

# LATAM corporate pool bias estimates
LATAM_TEAMS   = {"México", "Brasil", "Argentina", "Colombia", "Uruguay", "Ecuador"}
FAMOUS_EUROPE = {"España", "Francia", "Alemania", "Países Bajos", "Inglaterra", "Portugal"}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

ELO_RATINGS: dict[str, int] = {
    # Group A
    "México": 1836, "Sudáfrica": 1640, "Corea del Sur": 1800, "Chequia": 1762,
    # Group B
    "Canadá": 1783, "Bosnia": 1700, "Qatar": 1610, "Suiza": 1897,
    # Group C
    "Brasil": 1979, "Marruecos": 1820, "Haití": 1450, "Escocia": 1760,
    # Group D
    "USA": 1818, "Paraguay": 1740, "Australia": 1768, "Turquía": 1880,
    # Group E
    "Alemania": 1910, "Curazao": 1380, "Países Bajos": 1959, "Japón": 1879,
    # Group F
    "España": 2171, "Cabo Verde": 1590, "Bélgica": 1849, "Egipto": 1680,
    # Group G
    "Arabia Saudita": 1680, "Uruguay": 1890, "Irán": 1730, "Nueva Zelanda": 1560,
    # Group H
    "Francia": 2063, "Albania": 1650, "Portugal": 1976, "Argentina": 2113,
    # Group I
    "Inglaterra": 2042, "Croacia": 1933, "Ghana": 1660, "Panamá": 1650,
    # Group J
    "Colombia": 1998, "Ecuador": 1933, "Senegal": 1869, "Uzbekistán": 1580,
    # Group K
    "Italia": 1859, "Congo DR": 1550, "Serbia": 1820, "Jordania": 1620,
    # Group L
    "Dinamarca": 1864, "Costa Rica": 1700, "Iraq": 1620,
}


# ---------------------------------------------------------------------------
# Draw tendency: style-of-play factor
# ---------------------------------------------------------------------------

DRAW_TENDENCY: dict[str, float] = {
    # Draw-prone teams (positive values, range 0 to +1)
    "Bosnia":         0.8,
    "Irán":           0.7,
    "Marruecos":      0.6,
    "Costa Rica":     0.6,
    "Arabia Saudita": 0.5,
    # Decisive teams that tend to produce clear winners (negative values, -1 to 0)
    "Argentina":      -0.6,
    "España":         -0.5,
    "Francia":        -0.5,
    "Brasil":         -0.4,
    "Alemania":       -0.4,
    # All other teams implicitly default to 0.0 (neutral)
}


# ---------------------------------------------------------------------------
# Venue climate: average June temperatures per host city (°C)
# ---------------------------------------------------------------------------

VENUE_TEMP: dict[str, int] = {
    "Ciudad de México": 18,
    "Guadalajara":      22,
    "Monterrey":        35,
    "Dallas":           34,
    "Los Ángeles":      24,
    "San Francisco":    17,
    "Nueva York":       26,
    "Boston":           22,
    "Miami":            31,
    "Seattle":          18,
    "Kansas City":      28,
    "Atlanta":          28,
    "Toronto":          22,
    "Vancouver":        18,
}

# Confederation per team — used for climate and altitude adjustments
CONFEDERATION: dict[str, str] = {
    # UEFA (European teams — penalised in extreme heat)
    "España": "UEFA", "Francia": "UEFA", "Alemania": "UEFA",
    "Países Bajos": "UEFA", "Inglaterra": "UEFA", "Portugal": "UEFA",
    "Suiza": "UEFA", "Chequia": "UEFA", "Escocia": "UEFA",
    "Bosnia": "UEFA", "Albania": "UEFA", "Croacia": "UEFA",
    "Serbia": "UEFA", "Dinamarca": "UEFA", "Italia": "UEFA",
    "Bélgica": "UEFA", "Turquía": "UEFA",
    # CAF (African teams — warm-climate, penalised in cold venues)
    "Marruecos": "CAF", "Senegal": "CAF", "Egipto": "CAF",
    "Ghana": "CAF", "Congo DR": "CAF", "Sudáfrica": "CAF", "Cabo Verde": "CAF",
    # CONCACAF
    "México": "CONCACAF", "USA": "CONCACAF", "Canadá": "CONCACAF",
    "Curazao": "CONCACAF", "Haití": "CONCACAF", "Panamá": "CONCACAF",
    "Costa Rica": "CONCACAF",
    # CONMEBOL
    "Brasil": "CONMEBOL", "Argentina": "CONMEBOL", "Uruguay": "CONMEBOL",
    "Colombia": "CONMEBOL", "Ecuador": "CONMEBOL", "Paraguay": "CONMEBOL",
    # AFC
    "Corea del Sur": "AFC", "Japón": "AFC", "Irán": "AFC",
    "Arabia Saudita": "AFC", "Australia": "AFC", "Uzbekistán": "AFC",
    "Qatar": "AFC", "Jordania": "AFC", "Iraq": "AFC",
    # OFC
    "Nueva Zelanda": "OFC",
}

# Teams from habitually warm/humid climates — penalised when playing in cold venues (<20°C)
# Includes all CAF + tropical CONMEBOL (Brasil, Colombia, Ecuador)
WARM_CLIMATE_TEAMS: set[str] = {
    "Marruecos", "Senegal", "Egipto", "Ghana", "Congo DR", "Sudáfrica", "Cabo Verde",
    "Brasil", "Colombia", "Ecuador",
}


# ---------------------------------------------------------------------------
# Elo model
# ---------------------------------------------------------------------------

def elo_win_prob(rating_a: float, rating_b: float, boost: float = 0.0) -> float:
    """
    Standard Elo win probability for team A against team B.

    Parameters
    ----------
    rating_a : float
        Elo rating of team A.
    rating_b : float
        Elo rating of team B.
    boost : float
        Elo points added to team A (home / host advantage).

    Returns
    -------
    float
        Probability that team A wins (ignores draw).
    """
    dr = rating_a - rating_b + boost
    return 1.0 / (1.0 + 10.0 ** (-dr / 400.0))


def three_way_probs(
    rating_home: float,
    rating_away: float,
    is_host: bool = False,
    cards_penalty: Optional[dict] = None,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    venue: Optional[str] = None,
    travel_fatigue: Optional[dict] = None,
) -> dict[str, float]:
    """
    Convert Elo ratings into three-way (home win / draw / away win) probabilities,
    optionally adjusted for draw tendency, venue climate, and travel fatigue.

    Draw probability is modelled as a bell-shaped function of Elo difference,
    peaking when teams are evenly matched and decaying for large mismatches.

    Parameters
    ----------
    rating_home : float
    rating_away : float
    is_host : bool
        If True, applies the larger host-nation Elo boost.
    cards_penalty : dict, optional
        Per-team Elo penalty from accumulated cards / suspensions.
        Keys: 'home', 'away'.  Values are Elo points to subtract (positive = penalty).
        Example: {"home": 50, "away": 150}

    home_team : str, optional
        Team name for the home side.  Used to look up DRAW_TENDENCY and
        CONFEDERATION for climate adjustments.  If omitted, those features
        are skipped (fully retrocompatible).
    away_team : str, optional
        Team name for the away side.  Same as above.

    venue : str, optional
        Host-city name (must be a key in VENUE_TEMP).  Triggers climate
        Elo adjustments:
          - Temp > 28°C : UEFA teams receive -30 Elo.
          - Temp < 20°C : warm-climate teams (CAF / tropical CONMEBOL)
                          receive -20 Elo.
        Has no effect when home_team / away_team are not provided.

    travel_fatigue : dict, optional
        Per-team travel information.  Shape::

            {
                "home": {"hours": float, "rest_days": int},
                "away": {"hours": float, "rest_days": int},
            }

        Any team that travelled > 6 hours AND had < 4 rest days since
        their previous match receives a -40 Elo penalty.
        Only provide the sides that are affected; the other side is ignored.

    Returns
    -------
    dict with keys 'home', 'draw', 'away' summing to 1.0.

    Notes
    -----
    Draw-tendency adjustment:
        A joint factor is computed as the average of both teams' DRAW_TENDENCY
        values (defaulting to 0.0 for unlisted teams).  The base draw probability
        is then scaled by ``1 + 0.40 * joint_factor``, giving a maximum of +40%
        increase (both teams strongly draw-prone) or –40% reduction (both strongly
        decisive).  Adjustment is applied before floor/ceiling clamping.
    """
    # --- Cards / suspension penalties ------------------------------------------
    penalty = cards_penalty or {}
    effective_home = rating_home - penalty.get("home", 0)
    effective_away = rating_away - penalty.get("away", 0)

    # --- Climate adjustment (venue temperature) --------------------------------
    if venue and venue in VENUE_TEMP and home_team and away_team:
        temp = VENUE_TEMP[venue]
        home_conf = CONFEDERATION.get(home_team, "")
        away_conf = CONFEDERATION.get(away_team, "")

        if temp > 28:
            # Heat penalty for European teams unaccustomed to extreme warmth
            if home_conf == "UEFA":
                effective_home -= 30
            if away_conf == "UEFA":
                effective_away -= 30
        elif temp < 20:
            # Cold penalty for habitually warm-climate teams
            if home_team in WARM_CLIMATE_TEAMS:
                effective_home -= 20
            if away_team in WARM_CLIMATE_TEAMS:
                effective_away -= 20

    # --- Travel fatigue penalty ------------------------------------------------
    if travel_fatigue:
        for side, rating_attr in (("home", "effective_home"), ("away", "effective_away")):
            info = travel_fatigue.get(side, {})
            hours     = info.get("hours", 0.0)
            rest_days = info.get("rest_days", 99)
            if hours > 6 and rest_days < 4:
                if side == "home":
                    effective_home -= 40
                else:
                    effective_away -= 40

    # --- Base Elo probabilities ------------------------------------------------
    boost = ELO_BOOST_HOST if is_host else ELO_BOOST_STANDARD
    p_home_raw = elo_win_prob(effective_home, effective_away, boost)

    elo_diff = abs(effective_home - effective_away + boost)
    p_draw = 0.28 * math.exp(-((elo_diff / 600.0) ** 1.5))
    p_draw = min(p_draw, min(p_home_raw, 1.0 - p_home_raw) * 0.85)

    # --- Draw-tendency adjustment ----------------------------------------------
    if home_team and away_team:
        home_t = DRAW_TENDENCY.get(home_team, 0.0)
        away_t = DRAW_TENDENCY.get(away_team, 0.0)
        joint_factor = (home_t + away_t) / 2.0
        # Scale: +40% max increase (both +1.0), -40% max reduction (both -1.0)
        p_draw = p_draw * (1.0 + 0.40 * joint_factor)

    # --- Floor / ceiling and re-normalise --------------------------------------
    p_win  = max(0.03, p_home_raw - p_draw / 2.0)
    p_draw = max(0.05, p_draw)
    p_loss = max(0.03, 1.0 - p_win - p_draw)

    total = p_win + p_draw + p_loss
    return {
        "home": p_win  / total,
        "draw": p_draw / total,
        "away": p_loss / total,
    }


# ---------------------------------------------------------------------------
# Bivariate Poisson model
# ---------------------------------------------------------------------------

def expected_goals(
    rating_home: float,
    rating_away: float,
    boost: float = ELO_BOOST_STANDARD,
) -> tuple[float, float]:
    """
    Derive expected goals (λ) for each team from their Elo difference.

    Returns
    -------
    (lambda_home, lambda_away)
    """
    dr = (rating_home - rating_away + boost) / 400.0
    lambda_home = max(0.3, LAMBDA_BASE * (1.0 + 0.6 * dr))
    lambda_away = max(0.3, LAMBDA_BASE * (1.0 - 0.6 * dr))
    return lambda_home, lambda_away


def poisson_pmf(lam: float, k: int) -> float:
    """P(X = k) for X ~ Poisson(lam)."""
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def score_matrix(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 5,
) -> list[dict]:
    """
    Generate a probability distribution over scorelines (0-0 up to max-max).

    Returns
    -------
    List of dicts sorted by descending probability:
        [{"score": "1-0", "home": 1, "away": 0, "prob": 0.14}, ...]
    """
    scores = []
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob = poisson_pmf(lambda_home, h) * poisson_pmf(lambda_away, a)
            scores.append({"score": f"{h}-{a}", "home": h, "away": a, "prob": prob})
    return sorted(scores, key=lambda x: x["prob"], reverse=True)


# ---------------------------------------------------------------------------
# Expected value under 3/1/6 scoring system
# ---------------------------------------------------------------------------

@dataclass
class MatchEV:
    best_pick:    str    # e.g. "2-0" or "home_win"
    best_ev:      float
    ev_exact:     float  # EV of top scoreline
    top_score:    str    # Most probable scoreline
    top_score_p:  float
    ev_home_win:  float
    ev_draw:      float
    ev_away_win:  float
    prefer_exact: bool


def compute_ev(
    scores:  list[dict],
    probs:   dict[str, float],
    home:    str = "Home",
    away:    str = "Away",
) -> MatchEV:
    """
    Compute expected value for every possible bet under the 3/1/6 system.

    Since Prodemaster always asks for a scoreline, the decision is:
        - which scoreline to enter (you get 3pts if exact, 1pt if result correct)
    This function computes EV as: P(exact) * 3 + P(correct result but not exact) * 1

    Parameters
    ----------
    scores : output of score_matrix()
    probs  : output of three_way_probs()

    Returns
    -------
    MatchEV dataclass with optimal decision and all EVs.
    """
    def ev_for_score(s: dict) -> float:
        p_exact = s["prob"]
        # Probability correct result but not exact
        if s["home"] > s["away"]:
            p_result = probs["home"] - p_exact
        elif s["home"] == s["away"]:
            p_result = probs["draw"] - p_exact
        else:
            p_result = probs["away"] - p_exact
        p_result = max(0.0, p_result)
        return p_exact * POINTS["exact"] + p_result * POINTS["result"]

    # EV for each candidate scoreline
    scored_evs = [(s, ev_for_score(s)) for s in scores]
    best_score, best_ev = max(scored_evs, key=lambda x: x[1])

    top = scores[0]
    ev_top_exact = top["prob"] * POINTS["exact"]

    ev_home = probs["home"] * POINTS["result"]
    ev_draw = probs["draw"] * POINTS["result"]
    ev_away = probs["away"] * POINTS["result"]

    return MatchEV(
        best_pick    = best_score["score"],
        best_ev      = best_ev,
        ev_exact     = ev_top_exact,
        top_score    = top["score"],
        top_score_p  = top["prob"],
        ev_home_win  = ev_home,
        ev_draw      = ev_draw,
        ev_away_win  = ev_away,
        prefer_exact = best_ev > max(ev_home, ev_draw, ev_away),
    )


# ---------------------------------------------------------------------------
# Game theory: consensus bias for corporate LATAM pool
# ---------------------------------------------------------------------------

def consensus_bias(home_team: str, probs: dict[str, float]) -> dict[str, float]:
    """
    Estimate competitor consensus and compute edge vs model.

    Returns
    -------
    dict with 'consensus_home', 'edge' (model - consensus, negative = upset value).
    """
    bias = 0.0
    if home_team in LATAM_TEAMS:
        bias += 0.12
    if home_team in FAMOUS_EUROPE:
        bias += 0.08

    consensus_home = min(0.92, probs["home"] + bias)
    edge = probs["home"] - consensus_home  # negative = consensus overestimates home

    return {"consensus_home": consensus_home, "edge": edge}


# ---------------------------------------------------------------------------
# Convenience: full match analysis
# ---------------------------------------------------------------------------

def analyse_match(
    home:           str,
    away:           str,
    is_host:        bool = False,
    venue:          Optional[str] = None,
    travel_fatigue: Optional[dict] = None,
) -> dict:
    """
    Run full analysis for a single match.

    Parameters
    ----------
    home : str
        Home team name (must be a key in ELO_RATINGS or defaults to 1600).
    away : str
        Away team name.
    is_host : bool
        True if the home team is a 2026 host nation (applies larger Elo boost).
    venue : str, optional
        Host-city name (key in VENUE_TEMP).  Passed to three_way_probs() to
        trigger climate Elo adjustments.
    travel_fatigue : dict, optional
        Travel information for either or both teams.  Shape::

            {
                "home": {"hours": float, "rest_days": int},
                "away": {"hours": float, "rest_days": int},
            }

        Teams that travelled > 6 hours with < 4 rest days receive -40 Elo.

    Returns
    -------
    dict with keys: home, away, elo, probs, xg, top_scores, ev, consensus,
                    venue (if provided), adjustments_applied (list of strings).
    """
    r_home = ELO_RATINGS.get(home, 1600)
    r_away = ELO_RATINGS.get(away, 1600)

    boost  = ELO_BOOST_HOST if is_host else ELO_BOOST_STANDARD
    probs  = three_way_probs(
        r_home, r_away,
        is_host        = is_host,
        home_team      = home,
        away_team      = away,
        venue          = venue,
        travel_fatigue = travel_fatigue,
    )
    lh, la = expected_goals(r_home, r_away, boost)
    scores = score_matrix(lh, la)
    ev     = compute_ev(scores, probs, home, away)
    cons   = consensus_bias(home, probs)

    # Log which optional adjustments were active
    adjustments = []
    if venue:
        adjustments.append(f"climate:{venue}")
    if travel_fatigue:
        adjustments.append(f"travel_fatigue:{list(travel_fatigue.keys())}")
    if home in DRAW_TENDENCY or away in DRAW_TENDENCY:
        adjustments.append("draw_tendency")

    return {
        "home": home, "away": away,
        "elo": {"home": r_home, "away": r_away},
        "probs": probs,
        "xg": {"home": round(lh, 3), "away": round(la, 3)},
        "top_scores": scores[:6],
        "ev": ev,
        "consensus": cons,
        "venue": venue,
        "adjustments_applied": adjustments,
    }


# ---------------------------------------------------------------------------
# Quick CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    home = sys.argv[1] if len(sys.argv) > 1 else "México"
    away = sys.argv[2] if len(sys.argv) > 2 else "Sudáfrica"
    host = "--host" in sys.argv

    result = analyse_match(home, away, host)
    ev = result["ev"]
    p  = result["probs"]

    print(f"\n{'='*50}")
    print(f"  {home} vs {away}")
    print(f"{'='*50}")
    print(f"  Win:   {p['home']:.1%}  |  Draw: {p['draw']:.1%}  |  Loss: {p['away']:.1%}")
    print(f"  xG:    {result['xg']['home']} — {result['xg']['away']}")
    print(f"\n  Top scorelines:")
    for s in result["top_scores"][:4]:
        print(f"    {s['score']:>5}   {s['prob']:.1%}")
    print(f"\n  ✓ Optimal pick : {ev.best_pick}  (EV = {ev.best_ev:.3f} pts)")
    print(f"  Consensus edge : {result['consensus']['edge']:+.1%}")
    print()

    # ------------------------------------------------------------------
    # Example: draw-tendency + climate + travel fatigue in action
    # ------------------------------------------------------------------
    print("─" * 50)
    print("  Feature demo: Bosnia vs Irán  @  Monterrey")
    print("  (draw-prone teams + extreme heat venue)")
    print("─" * 50)
    demo = analyse_match(
        home           = "Bosnia",
        away           = "Irán",
        venue          = "Monterrey",   # 35°C — UEFA gets -30 Elo (neither team is UEFA here)
        travel_fatigue = {
            "away": {"hours": 9.5, "rest_days": 3},  # Irán: long flight + short rest → -40 Elo
        },
    )
    dp = demo["probs"]
    print(f"  Draw prob (with draw-tendency boost): {dp['draw']:.1%}")
    print(f"  Home win : {dp['home']:.1%}  |  Away win: {dp['away']:.1%}")
    print(f"  Adjustments active: {demo['adjustments_applied']}")

    print()
    print("─" * 50)
    print("  Feature demo: Francia vs Sudáfrica  @  Dallas")
    print("  (UEFA team in heat → -30 Elo, warm-climate team no penalty)")
    print("─" * 50)
    demo2 = analyse_match(
        home  = "Francia",
        away  = "Sudáfrica",
        venue = "Dallas",  # 34°C — Francia (UEFA) gets -30 Elo
    )
    dp2 = demo2["probs"]
    print(f"  Home win : {dp2['home']:.1%}  |  Draw: {dp2['draw']:.1%}  |  Away win: {dp2['away']:.1%}")
    print(f"  Adjustments active: {demo2['adjustments_applied']}")
    print()
