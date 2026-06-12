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
) -> dict[str, float]:
    """
    Convert Elo ratings into three-way (home win / draw / away win) probabilities.

    Draw probability is modelled as a bell-shaped function of Elo difference,
    peaking when teams are evenly matched and decaying for large mismatches.

    Parameters
    ----------
    rating_home : float
    rating_away : float
    is_host : bool
        If True, applies the larger host-nation Elo boost.

    Returns
    -------
    dict with keys 'home', 'draw', 'away'.
    """
    boost = ELO_BOOST_HOST if is_host else ELO_BOOST_STANDARD
    p_home_raw = elo_win_prob(rating_home, rating_away, boost)

    elo_diff = abs(rating_home - rating_away + boost)
    p_draw = 0.28 * math.exp(-((elo_diff / 600.0) ** 1.5))
    p_draw = min(p_draw, min(p_home_raw, 1.0 - p_home_raw) * 0.85)

    p_win  = max(0.03, p_home_raw - p_draw / 2.0)
    p_draw = max(0.05, p_draw)
    p_loss = max(0.03, 1.0 - p_win - p_draw)

    # Re-normalise to sum to 1
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
    home:    str,
    away:    str,
    is_host: bool = False,
) -> dict:
    """
    Run full analysis for a single match.

    Returns a dict with: probs, xg, scores, ev, consensus.
    """
    r_home = ELO_RATINGS.get(home, 1600)
    r_away = ELO_RATINGS.get(away, 1600)

    boost  = ELO_BOOST_HOST if is_host else ELO_BOOST_STANDARD
    probs  = three_way_probs(r_home, r_away, is_host)
    lh, la = expected_goals(r_home, r_away, boost)
    scores = score_matrix(lh, la)
    ev     = compute_ev(scores, probs, home, away)
    cons   = consensus_bias(home, probs)

    return {
        "home": home, "away": away,
        "elo": {"home": r_home, "away": r_away},
        "probs": probs,
        "xg": {"home": round(lh, 3), "away": round(la, 3)},
        "top_scores": scores[:6],
        "ev": ev,
        "consensus": cons,
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
