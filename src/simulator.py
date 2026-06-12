"""
wc2026_quiniela.simulator
-------------------------
Monte Carlo simulation of the full World Cup 2026 tournament.
Runs N simulations to estimate each team's probability of reaching
each stage: group exit, Round of 32, Round of 16, QF, SF, Final, Champion.
"""

import random
import numpy as np
from collections import defaultdict
from typing import Optional
from model import (
    ELO_RATINGS, three_way_probs, score_matrix,
    expected_goals, ELO_BOOST_STANDARD
)


# ---------------------------------------------------------------------------
# Tournament structure
# ---------------------------------------------------------------------------

GROUPS: dict[str, list[str]] = {
    "A": ["México", "Sudáfrica", "Corea del Sur", "Chequia"],
    "B": ["Canadá", "Bosnia", "Qatar", "Suiza"],
    "C": ["Brasil", "Marruecos", "Haití", "Escocia"],
    "D": ["USA", "Paraguay", "Australia", "Turquía"],
    "E": ["Alemania", "Curazao", "Países Bajos", "Japón"],
    "F": ["España", "Cabo Verde", "Bélgica", "Egipto"],
    "G": ["Arabia Saudita", "Uruguay", "Irán", "Nueva Zelanda"],
    "H": ["Francia", "Albania", "Portugal", "Argentina"],
    "I": ["Inglaterra", "Croacia", "Ghana", "Panamá"],
    "J": ["Colombia", "Ecuador", "Senegal", "Uzbekistán"],
    "K": ["Italia", "Congo DR", "Serbia", "Jordania"],
    "L": ["Dinamarca", "Costa Rica", "Iraq", "Haití"],
}

HOST_NATIONS = {"México", "USA", "Canadá"}


# ---------------------------------------------------------------------------
# Match simulation
# ---------------------------------------------------------------------------

def simulate_match(
    home: str,
    away: str,
    is_host: bool = False,
    neutral: bool = True,
) -> tuple[int, int]:
    """
    Simulate a single match. Returns (home_goals, away_goals).
    Uses Poisson-distributed goals with Elo-derived lambdas.
    """
    boost = (ELO_BOOST_STANDARD // 2) if neutral else (100 if is_host else ELO_BOOST_STANDARD)
    r_h = ELO_RATINGS.get(home, 1600)
    r_a = ELO_RATINGS.get(away, 1600)
    lh, la = expected_goals(r_h, r_a, boost)
    return np.random.poisson(lh), np.random.poisson(la)


def simulate_match_knockout(home: str, away: str) -> str:
    """
    Simulate knockout match. Returns winner (uses penalties if draw after 90).
    """
    gh, ga = simulate_match(home, away, neutral=True)
    if gh != ga:
        return home if gh > ga else away
    # Extra time / penalties: use Elo-based coin flip
    r_h = ELO_RATINGS.get(home, 1600)
    r_a = ELO_RATINGS.get(away, 1600)
    p_h = 1.0 / (1.0 + 10.0 ** (-(r_h - r_a) / 400.0))
    return home if random.random() < p_h else away


# ---------------------------------------------------------------------------
# Group stage simulation
# ---------------------------------------------------------------------------

def simulate_group(teams: list[str]) -> list[str]:
    """
    Simulate a single group. Returns teams sorted by final standing
    (top 2 advance automatically; returns all 4 ranked).

    Points: W=3, D=1, L=0. Tiebreaker: goal difference, then goals scored.
    """
    pts  = defaultdict(int)
    gd   = defaultdict(int)
    gf   = defaultdict(int)

    # Round-robin: each pair plays once
    for i, home in enumerate(teams):
        for away in teams[i + 1:]:
            is_host = home in HOST_NATIONS
            gh, ga = simulate_match(home, away, is_host=is_host, neutral=False)
            gf[home] += gh; gf[away] += ga
            gd[home] += gh - ga; gd[away] += ga - gh
            if gh > ga:
                pts[home] += 3
            elif gh == ga:
                pts[home] += 1; pts[away] += 1
            else:
                pts[away] += 3

    # Sort: pts → gd → gf → random tiebreak
    ranked = sorted(
        teams,
        key=lambda t: (pts[t], gd[t], gf[t], random.random()),
        reverse=True,
    )
    return ranked  # index 0 = 1st, 1 = 2nd, etc.


# ---------------------------------------------------------------------------
# Full tournament simulation
# ---------------------------------------------------------------------------

def simulate_tournament() -> dict[str, str]:
    """
    Simulate one full tournament. Returns {team: best_stage_reached}.
    Stages: 'group', 'R32', 'R16', 'QF', 'SF', 'Final', 'Champion'
    """
    stage = {t: "group" for t in ELO_RATINGS}

    # --- Group stage ---
    group_results: dict[str, list[str]] = {}
    for g, teams in GROUPS.items():
        ranked = simulate_group(teams)
        group_results[g] = ranked
        stage[ranked[0]] = "R32"
        stage[ranked[1]] = "R32"

    # Best 3rd-place finishers (simplified: take 8 best 3rds by Elo)
    thirds = [group_results[g][2] for g in GROUPS]
    thirds_sorted = sorted(thirds, key=lambda t: ELO_RATINGS.get(t, 0), reverse=True)
    for t in thirds_sorted[:8]:
        stage[t] = "R32"

    # Build R32 bracket (simplified: group winners vs runners-up)
    # Full bracket pairing follows FIFA rules; simplified here
    r32_teams = [t for t, s in stage.items() if s == "R32"]

    def run_stage(teams: list[str], stage_name: str) -> list[str]:
        random.shuffle(teams)
        winners = []
        for i in range(0, len(teams) - 1, 2):
            w = simulate_match_knockout(teams[i], teams[i + 1])
            stage[w] = stage_name
            winners.append(w)
        return winners

    r16 = run_stage(r32_teams, "R16")
    qf  = run_stage(r16, "QF")
    sf  = run_stage(qf, "SF")

    # Final
    if len(sf) >= 2:
        champion = simulate_match_knockout(sf[0], sf[1])
        stage[champion] = "Champion"
        runner_up = sf[1] if champion == sf[0] else sf[0]
        stage[runner_up] = "Final"

    return stage


# ---------------------------------------------------------------------------
# Monte Carlo runner
# ---------------------------------------------------------------------------

def run_monte_carlo(n: int = 10_000, seed: Optional[int] = 42) -> dict[str, dict[str, float]]:
    """
    Run N tournament simulations. Returns probability of each team
    reaching each stage.

    Returns
    -------
    {team: {"group": 0.05, "R32": 0.80, ..., "Champion": 0.12}}
    """
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    STAGES = ["group", "R32", "R16", "QF", "SF", "Final", "Champion"]
    counts: dict[str, dict[str, int]] = {
        t: {s: 0 for s in STAGES} for t in ELO_RATINGS
    }

    for _ in range(n):
        result = simulate_tournament()
        for team, best_stage in result.items():
            # Count all stages up to and including best_stage
            reached = STAGES.index(best_stage)
            for s in STAGES[:reached + 1]:
                counts[team][s] += 1

    probs = {
        team: {s: counts[team][s] / n for s in STAGES}
        for team in counts
    }
    return probs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    print("Running 10,000 tournament simulations...")
    results = run_monte_carlo(n=10_000)

    # Print champion probabilities sorted
    champ_probs = sorted(
        [(t, p["Champion"]) for t, p in results.items()],
        key=lambda x: x[1], reverse=True
    )

    print(f"\n{'Team':<20} {'Champion':>10} {'Final':>10} {'SF':>8} {'QF':>8}")
    print("-" * 58)
    for team, p_champ in champ_probs[:15]:
        r = results[team]
        print(
            f"{team:<20} {p_champ:>9.1%} "
            f"{r['Final']:>9.1%} "
            f"{r['SF']:>7.1%} "
            f"{r['QF']:>7.1%}"
        )
