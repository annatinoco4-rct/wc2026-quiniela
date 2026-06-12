"""
wc2026_quiniela.strategy
------------------------
Game theory layer: optimize quiniela picks given competitor biases
in a corporate LATAM pool (~100 participants).

Core insight: winning a pool ≠ predicting accurately.
It requires maximizing RELATIVE performance vs predictably irrational competitors.

Reference: Keynes beauty contest + Kelly-like EV maximization.
"""

import numpy as np
from typing import Optional
from model import analyse_match, LATAM_TEAMS, FAMOUS_EUROPE, POINTS


# ---------------------------------------------------------------------------
# Competitor bias model
# ---------------------------------------------------------------------------

POOL_PROFILE = {
    "size": 101,
    "latam_bias": 0.12,       # Inflation for LATAM home teams
    "european_bias": 0.08,    # Inflation for famous European clubs
    "host_extra_bias": 0.10,  # Extra bias for tournament hosts (MEX/USA/CAN)
    "recency_bias": 0.05,     # Slight inflation for recent tournament winners
    "recent_winners": {"Argentina", "Francia"},
}


def estimate_consensus(
    home: str,
    away: str,
    model_probs: dict[str, float],
) -> dict[str, float]:
    """
    Estimate what the Avera pool will predict for this match.
    Returns {'home': ..., 'draw': ..., 'away': ...} — a biased probability vector.
    """
    bias = 0.0

    if home in LATAM_TEAMS:
        bias += POOL_PROFILE["latam_bias"]
    if home in FAMOUS_EUROPE:
        bias += POOL_PROFILE["european_bias"]
    if home in POOL_PROFILE["recent_winners"]:
        bias += POOL_PROFILE["recency_bias"]

    consensus_home = min(0.92, model_probs["home"] + bias)
    # Redistribute remaining probability proportionally
    remaining = 1.0 - consensus_home
    original_non_home = model_probs["draw"] + model_probs["away"]
    scale = remaining / original_non_home if original_non_home > 0 else 1.0

    return {
        "home":  consensus_home,
        "draw":  model_probs["draw"]  * scale,
        "away":  model_probs["away"]  * scale,
    }


# ---------------------------------------------------------------------------
# EV adjusted for pool competition
# ---------------------------------------------------------------------------

def pool_adjusted_ev(
    model_probs:     dict[str, float],
    consensus_probs: dict[str, float],
    score_probs:     list[dict],
    pool_size:       int = 101,
) -> dict[str, float]:
    """
    Compute pool-adjusted EV for each possible pick.

    Standard EV = P(event) * points
    Pool EV     = P(event) * points * (1 / expected_competitors_sharing_points)

    When many competitors make the same pick, each point is worth less
    in relative ranking. Contrarian correct picks gain more ground.

    Returns dict of {pick_label: pool_ev} for key picks.
    """
    def sharing_factor(pick_prob_in_pool: float) -> float:
        """How many competitors share this pick on average?"""
        expected_sharers = pick_prob_in_pool * pool_size
        return 1.0 / max(1.0, expected_sharers)

    evs = {}

    # Result picks
    for result, label in [("home", "Gana local"), ("draw", "Empate"), ("away", "Gana visitante")]:
        model_p    = model_probs[result]
        pool_p     = consensus_probs[result]
        base_ev    = model_p * POINTS["result"]
        pool_ev    = base_ev * sharing_factor(pool_p)
        evs[label] = {"model_ev": base_ev, "pool_ev": pool_ev, "pool_p": pool_p}

    # Top 3 scorelines
    for s in score_probs[:3]:
        label   = f"Exacto {s['score']}"
        base_ev = s["prob"] * POINTS["exact"]
        # Assume fewer people bet exact scores — lower consensus density
        pool_p  = s["prob"] * 0.3  # ~30% of people who pick this result also pick this score
        pool_ev = base_ev * sharing_factor(pool_p)
        evs[label] = {"model_ev": base_ev, "pool_ev": pool_ev, "pool_p": pool_p}

    return evs


# ---------------------------------------------------------------------------
# Champion pick strategy
# ---------------------------------------------------------------------------

CHAMPION_PROBS = {
    "España":          0.19,
    "Argentina":       0.16,
    "Francia":         0.16,
    "Inglaterra":      0.11,
    "Portugal":        0.08,
    "Brasil":          0.08,
    "Países Bajos":    0.06,
    "Alemania":        0.05,
    "Colombia":        0.04,
    "Croacia":         0.03,
}

CHAMPION_CONSENSUS = {
    "Argentina": 0.22,   # LATAM bias inflates this heavily
    "Brasil":    0.18,
    "Francia":   0.14,
    "España":    0.12,
    "México":    0.08,   # Local hero effect
    "Portugal":  0.07,
    "Alemania":  0.05,
    "Inglaterra": 0.04,
    "Colombia":  0.05,
    "Croacia":   0.01,
}


def champion_strategy(pool_size: int = 101) -> list[dict]:
    """
    Rank champion picks by pool-adjusted EV.

    Pool EV of champion pick = P(champion) * 6 * (1 / expected_sharers)
    """
    results = []
    for team, p_model in CHAMPION_PROBS.items():
        p_consensus = CHAMPION_CONSENSUS.get(team, p_model)
        expected_sharers = p_consensus * pool_size
        pool_ev = p_model * POINTS["champion"] / max(1.0, expected_sharers)
        base_ev = p_model * POINTS["champion"]
        edge    = p_model - p_consensus

        results.append({
            "team":             team,
            "model_prob":       p_model,
            "consensus_prob":   p_consensus,
            "edge":             edge,
            "base_ev":          base_ev,
            "pool_ev":          pool_ev,
            "recommendation":   "VALUE" if edge > 0 else "AVOID",
        })

    return sorted(results, key=lambda x: x["pool_ev"], reverse=True)


# ---------------------------------------------------------------------------
# Full match recommendation
# ---------------------------------------------------------------------------

def recommend_pick(
    home:    str,
    away:    str,
    is_host: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Full strategic recommendation for a single match pick.

    Combines model EV + pool-adjusted EV + consensus edge.
    """
    analysis   = analyse_match(home, away, is_host)
    consensus  = estimate_consensus(home, away, analysis["probs"])
    pool_evs   = pool_adjusted_ev(
        analysis["probs"], consensus, analysis["top_scores"]
    )

    best_pick  = max(pool_evs, key=lambda k: pool_evs[k]["pool_ev"])
    best_ev    = pool_evs[best_pick]

    result = {
        "match":       f"{home} vs {away}",
        "optimal_pick": best_pick,
        "pool_ev":      best_ev["pool_ev"],
        "model_ev":     best_ev["model_ev"],
        "consensus":    consensus,
        "all_evs":      pool_evs,
        "analysis":     analysis,
    }

    if verbose:
        p = analysis["probs"]
        ev = analysis["ev"]
        print(f"\n{'─'*52}")
        print(f"  {home} vs {away}")
        print(f"{'─'*52}")
        print(f"  Modelo    : {home} {p['home']:.0%} | Empate {p['draw']:.0%} | {away} {p['away']:.0%}")
        print(f"  Consenso  : {home} {consensus['home']:.0%} | Empate {consensus['draw']:.0%} | {away} {consensus['away']:.0%}")
        print(f"  Pick óptimo (pool EV): {best_pick}  →  {best_ev['pool_ev']:.4f}")
        print(f"  Marcador sugerido     : {ev.best_pick}")
        print()

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n=== ESTRATEGIA CAMPEÓN ===\n")
    champ = champion_strategy()
    print(f"{'Equipo':<18} {'P(mod)':>8} {'P(pool)':>8} {'Edge':>8} {'EV base':>8} {'EV pool':>8} {'Rec':>8}")
    print("─" * 72)
    for r in champ:
        print(
            f"{r['team']:<18} {r['model_prob']:>7.0%} {r['consensus_prob']:>7.0%} "
            f"{r['edge']:>+7.0%} {r['base_ev']:>8.3f} {r['pool_ev']:>8.4f} {r['recommendation']:>8}"
        )

    print("\n=== PICKS SEMANA 1 ===")
    matches = [
        ("México", "Sudáfrica", True),
        ("Corea del Sur", "Chequia", False),
        ("Canadá", "Bosnia", True),
        ("USA", "Paraguay", True),
        ("Brasil", "Marruecos", False),
        ("España", "Cabo Verde", False),
    ]
    for home, away, host in matches:
        recommend_pick(home, away, host)
