"""
gameday.py
----------
T-60min gameday pipeline: resolves the 365scores fixture, pulls the
confirmed/likely lineup, penalises Elo for absent or benched key players
(lineup_fetcher.PLAYER_IMPACT), and re-runs the full Elo + Poisson + pool-EV
model (model.py / strategy.py) with the adjusted ratings.

Run it ~60 minutes before kickoff, once lineups are typically confirmed:

    python src/gameday.py México Sudáfrica 2026-06-11 --host

If lineups aren't confirmed yet (or the API/fixture lookup fails for any
reason), the pipeline falls back to the unadjusted base Elo and says so —
it never hard-fails the whole report over a lineup fetch problem.
"""

from __future__ import annotations

import sys
from dataclasses import asdict

from model import (
    ELO_RATINGS,
    ELO_BOOST_HOST,
    ELO_BOOST_STANDARD,
    three_way_probs,
    expected_goals,
    score_matrix,
    compute_ev,
)
from strategy import estimate_consensus, pool_adjusted_ev
from lineup_fetcher import get_game_id, fetch_lineup, adjusted_elo, LineupFetchError, PLAYER_IMPACT


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def analyse_with_lineups(home: str, away: str, date: str, is_host: bool = False) -> dict:
    """
    Full T-60 pipeline for a single match.

    Steps
    -----
    1. Resolve gameId from team names + date (365scores fixtures).
    2. Pull the confirmed/likely lineup for both sides.
    3. Penalise each side's Elo for missing/benched PLAYER_IMPACT entries.
    4. Re-run three_way_probs / expected_goals / score_matrix / compute_ev
       with the adjusted ratings, then layer the pool-adjusted EV
       (strategy.py's competitor-bias model) on top.

    Note: this calls model.py's lower-level functions directly with explicit
    numeric ratings (rather than model.analyse_match(), which always does its
    own ELO_RATINGS[team] lookup) — that's the cleanest way to inject a
    lineup-based adjustment without monkeypatching module state or forking
    the model's core math.

    Returns
    -------
    dict with elo_base, elo_adjusted, elo_delta, lineup, probs, top_scores,
    ev (model.MatchEV), consensus, pool_best_pick, pool_ev, and warnings.
    """
    base_home = ELO_RATINGS.get(home, 1600)
    base_away = ELO_RATINGS.get(away, 1600)

    game_id = None
    lineup = None
    warnings: list[str] = []

    try:
        game_id = get_game_id(home, away, date)
        lineup = fetch_lineup(game_id)
    except (LineupFetchError, LookupError, ValueError) as exc:
        warnings.append(f"No se pudo obtener alineación ({exc}). Usando Elo base sin ajustar.")

    if lineup:
        home_elo = adjusted_elo(home, lineup["home"], base_home)
        away_elo = adjusted_elo(away, lineup["away"], base_away)
        for side, team, confirmed in (("home", home, lineup["home_confirmed"]),
                                       ("away", away, lineup["away_confirmed"])):
            if not confirmed:
                warnings.append(f"Alineación de {team} aún NO confirmada — puede cambiar.")
    else:
        home_elo, away_elo = base_home, base_away

    boost = ELO_BOOST_HOST if is_host else ELO_BOOST_STANDARD
    probs = three_way_probs(home_elo, away_elo, is_host=is_host, home_team=home, away_team=away)
    lh, la = expected_goals(home_elo, away_elo, boost)
    scores = score_matrix(lh, la)
    ev = compute_ev(scores, probs, home, away)

    consensus = estimate_consensus(home, away, probs)
    pool_evs = pool_adjusted_ev(probs, consensus, scores)
    best_pick = max(pool_evs, key=lambda k: pool_evs[k]["pool_ev"])

    return {
        "home": home, "away": away, "date": date, "game_id": game_id,
        "elo_base": {"home": round(base_home, 1), "away": round(base_away, 1)},
        "elo_adjusted": {"home": round(home_elo, 1), "away": round(away_elo, 1)},
        "elo_delta": {"home": round(home_elo - base_home, 1), "away": round(away_elo - base_away, 1)},
        "lineup": lineup,
        "probs": probs,
        "top_scores": scores[:5],
        "ev": ev,
        "consensus": consensus,
        "pool_best_pick": best_pick,
        "pool_ev": pool_evs[best_pick],
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Absent / benched key-player summary (for the report)
# ---------------------------------------------------------------------------

def _missing_key_players(team: str, lineup: list) -> list[str]:
    """List PLAYER_IMPACT players for *team* who are absent or benched."""
    if not lineup:
        return []
    from lineup_fetcher import _strip_accents  # local helper, not part of public API

    names = {_strip_accents(p["name"]).lower(): p["status"] for p in lineup}
    flags = []
    for player, info in PLAYER_IMPACT.items():
        if info["team"] != team:
            continue
        surname = _strip_accents(player.split()[-1]).lower()
        status = next((s for name, s in names.items() if surname in name), None)
        if status is None:
            flags.append(f"{player} — AUSENTE (-{info['elo_weight']} Elo)")
        elif status == "substitute":
            flags.append(f"{player} — banca (-{info['elo_weight'] * 0.5:.0f} Elo)")
    return flags


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(result: dict) -> None:
    home, away = result["home"], result["away"]
    p = result["probs"]
    ev = result["ev"]

    print(f"\n{'='*58}")
    print(f"  GAMEDAY T-60  —  {home} vs {away}  ({result['date']})")
    print(f"{'='*58}")

    if result["game_id"]:
        print(f"  gameId 365scores : {result['game_id']}")
    for w in result["warnings"]:
        print(f"  ⚠ {w}")

    eb, ea = result["elo_base"], result["elo_adjusted"]
    ed = result["elo_delta"]
    print(f"\n  Elo base      : {home} {eb['home']}   |   {away} {eb['away']}")
    print(f"  Elo ajustado  : {home} {ea['home']} ({ed['home']:+.1f})   |   "
          f"{away} {ea['away']} ({ed['away']:+.1f})")

    if result["lineup"]:
        for team, side in ((home, "home"), (away, "away")):
            flags = _missing_key_players(team, result["lineup"][side])
            if flags:
                print(f"\n  Bajas/riesgos {team}:")
                for f in flags:
                    print(f"    - {f}")

    print(f"\n  Prob. (ajustado): {home} {p['home']:.0%}  |  Empate {p['draw']:.0%}  |  {away} {p['away']:.0%}")
    print(f"  Top marcadores:")
    for s in result["top_scores"]:
        print(f"    {s['score']:>5}   {s['prob']:.1%}")

    print(f"\n  EV óptimo (modelo)  : {ev.best_pick}  (EV = {ev.best_ev:.3f} pts)")
    print(f"  Pick óptimo (pool)  : {result['pool_best_pick']}  "
          f"(pool EV = {result['pool_ev']['pool_ev']:.4f}, model EV = {result['pool_ev']['model_ev']:.3f})")
    print(f"  Consenso esperado   : {home} {result['consensus']['home']:.0%}  |  "
          f"Empate {result['consensus']['draw']:.0%}  |  {away} {result['consensus']['away']:.0%}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python src/gameday.py <local> <visitante> <fecha:YYYY-MM-DD> [--host]")
        print("Ej.:  python src/gameday.py México Sudáfrica 2026-06-11 --host")
        sys.exit(1)

    home_arg, away_arg, date_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    host_flag = "--host" in sys.argv

    outcome = analyse_with_lineups(home_arg, away_arg, date_arg, is_host=host_flag)
    print_report(outcome)
