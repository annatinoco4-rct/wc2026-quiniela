"""
elo_updater.py
--------------
Updates team Elo ratings using actual World Cup tournament results.

Formula:
    R_new = R_old + K × (S - E)
    E     = 1 / (1 + 10 ^ ((R_opponent - R_own) / 400))

K values:
    K = 20 for group-stage matches
    K = 30 for knockout matches (round of 32 onwards)
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

# ---------------------------------------------------------------------------
# Name mapping: CSV names (English) → display names (Spanish)
# ---------------------------------------------------------------------------
NAME_MAP: Dict[str, str] = {
    "Mexico": "México",
    "South Korea": "Corea del Sur",
    "Korea Republic": "Corea del Sur",
    "Czech Republic": "Chequia",
    "Czechia": "Chequia",
    "United States": "USA",
    "Bosnia-Herzegovina": "Bosnia",
    "Ivory Coast": "Costa de Marfil",
    "Cote d'Ivoire": "Costa de Marfil",
    "DR Congo": "Congo DR",
    "Democratic Republic of Congo": "Congo DR",
    "Saudi Arabia": "Arabia Saudita",
    "New Zealand": "Nueva Zelanda",
    "Cape Verde Islands": "Cabo Verde",
    "Cape Verde": "Cabo Verde",
    "South Africa": "Sudáfrica",
    "Canada": "Canadá",
    "Switzerland": "Suiza",
    "Brazil": "Brasil",
    "Haiti": "Haití",
    "Turkey": "Turquía",
    "Germany": "Alemania",
    "Netherlands": "Países Bajos",
    "Sweden": "Suecia",
    "Spain": "España",
    "Belgium": "Bélgica",
    "Iran": "Irán",
    "France": "Francia",
    "Norway": "Noruega",
    "Algeria": "Argelia",
    "Austria": "Austria",
    "England": "Inglaterra",
    "Panama": "Panamá",
    "Uzbekistan": "Uzbekistán",
    "Scotland": "Escocia",
    "Morocco": "Marruecos",
    "Tunisia": "Túnez",
    "Egypt": "Egipto",
    "Jordan": "Jordania",
    "Curaçao": "Curazao",
    "Croatia": "Croacia",
    "Denmark": "Dinamarca",
    "Costa Rica": "Costa Rica",
    "Iraq": "Iraq",
    "Senegal": "Senegal",
    "Ecuador": "Ecuador",
    "Colombia": "Colombia",
    "Ghana": "Ghana",
    "Serbia": "Serbia",
    "Portugal": "Portugal",
    "Argentina": "Argentina",
    "Uruguay": "Uruguay",
    "Japan": "Japón",
    "Australia": "Australia",
    "Paraguay": "Paraguay",
    "Qatar": "Qatar",
    "Trinidad and Tobago": "Trinidad",
    "Central African Republic": "Rep. Centroafricana",
    "Burkina Faso": "Burkina Faso",
}

# ---------------------------------------------------------------------------
# K-factor by round
# ---------------------------------------------------------------------------
K_BY_ROUND: Dict[str, int] = {
    "group": 20,
    "round of 32": 30,
    "round of 16": 30,
    "quarterfinal": 30,
    "semifinal": 30,
    "third place": 30,
    "final": 30,
}
DEFAULT_K = 20


def _normalize(name: str) -> str:
    """Return the display name for a team, applying NAME_MAP if available."""
    return NAME_MAP.get(name.strip(), name.strip())


def _expected_score(own_elo: float, opp_elo: float) -> float:
    """Probability that the team with *own_elo* beats the one with *opp_elo*."""
    return 1.0 / (1.0 + 10 ** ((opp_elo - own_elo) / 400.0))


def _actual_scores(home_goals: int, away_goals: int) -> tuple[float, float]:
    """Return (home_S, away_S) where S ∈ {1, 0.5, 0}."""
    if home_goals > away_goals:
        return 1.0, 0.0
    elif home_goals < away_goals:
        return 0.0, 1.0
    else:
        return 0.5, 0.5


def _k_factor(round_str: str) -> int:
    """Derive K from the round column (case-insensitive, partial match)."""
    key = round_str.strip().lower()
    for pattern, k in K_BY_ROUND.items():
        if pattern in key:
            return k
    return DEFAULT_K


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_elos(path: Path) -> Dict[str, float]:
    """
    Load initial Elo ratings from a CSV file.

    Expected columns (order-independent): team, elo
    Accepts both English and Spanish team names — applies NAME_MAP on load.
    """
    elos: Dict[str, float] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            team = _normalize(row["team"])
            elos[team] = float(row["elo"])
    return elos


def _load_results(path: Path) -> list[dict]:
    """
    Load match results from a CSV file, sorted chronologically.

    Expected columns: date, home, away, home_goals, away_goals, group, round
    """
    results = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            results.append(
                {
                    "date": row["date"].strip(),
                    "home": _normalize(row["home"]),
                    "away": _normalize(row["away"]),
                    "home_goals": int(row["home_goals"]),
                    "away_goals": int(row["away_goals"]),
                    "group": row.get("group", "").strip(),
                    "round": row.get("round", "group").strip(),
                }
            )
    # Sort chronologically (ISO date strings sort correctly lexicographically)
    results.sort(key=lambda r: r["date"])
    return results


# ---------------------------------------------------------------------------
# Core update logic
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent   # project root
ELO_CSV = BASE_DIR / "data" / "elo_ratings.csv"
RESULTS_CSV = BASE_DIR / "data" / "results.csv"
UPDATED_CSV = BASE_DIR / "data" / "elo_ratings_updated.csv"


def update_elos(
    elo_path: Path = ELO_CSV,
    results_path: Path = RESULTS_CSV,
) -> Dict[str, float]:
    """
    Process every match in *results_path* chronologically and update Elo
    ratings read from *elo_path*.

    Returns
    -------
    dict
        Mapping {team_name: updated_elo}.  Teams not appearing in any match
        retain their initial rating.
    """
    elos = _load_elos(elo_path)
    matches = _load_results(results_path)

    for match in matches:
        home = match["home"]
        away = match["away"]

        # Skip if either team is not in the ratings file
        if home not in elos:
            print(f"[WARN] Team not found in ratings: '{home}' — skipping {match['date']}")
            continue
        if away not in elos:
            print(f"[WARN] Team not found in ratings: '{away}' — skipping {match['date']}")
            continue

        r_home = elos[home]
        r_away = elos[away]

        e_home = _expected_score(r_home, r_away)
        e_away = _expected_score(r_away, r_home)

        s_home, s_away = _actual_scores(match["home_goals"], match["away_goals"])

        k = _k_factor(match["round"])

        elos[home] = r_home + k * (s_home - e_home)
        elos[away] = r_away + k * (s_away - e_away)

    return elos


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def save_updated_elos(
    path: Path = UPDATED_CSV,
    elo_path: Path = ELO_CSV,
    results_path: Path = RESULTS_CSV,
) -> None:
    """
    Compute updated Elos and save them to *path* as a CSV with columns:
    team, elo
    """
    updated = update_elos(elo_path, results_path)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["team", "elo"])
        for team, elo in sorted(updated.items(), key=lambda x: -x[1]):
            writer.writerow([team, f"{elo:.2f}"])

    print(f"Updated Elo ratings saved to: {path}")


def elo_diff_report(
    elo_path: Path = ELO_CSV,
    results_path: Path = RESULTS_CSV,
) -> None:
    """
    Print a formatted table of teams ordered by Elo delta (descending).

    Columns: Team | Initial Elo | Updated Elo | Δ
    """
    initial = _load_elos(elo_path)
    updated = update_elos(elo_path, results_path)

    diffs = []
    for team, elo_new in updated.items():
        elo_old = initial.get(team, elo_new)
        delta = elo_new - elo_old
        diffs.append((team, elo_old, elo_new, delta))

    # Sort by delta descending (biggest gainers first)
    diffs.sort(key=lambda x: -x[3])

    col_w = 24
    header = (
        f"{'Team':<{col_w}}  "
        f"{'Initial':>10}  "
        f"{'Updated':>10}  "
        f"{'Δ':>8}"
    )
    separator = "-" * len(header)

    print("\n" + separator)
    print("  Elo Rating Changes — Post-Tournament Recalibration")
    print(separator)
    print(header)
    print(separator)

    for team, elo_old, elo_new, delta in diffs:
        sign = "+" if delta >= 0 else ""
        print(
            f"{team:<{col_w}}  "
            f"{elo_old:>10.1f}  "
            f"{elo_new:>10.1f}  "
            f"{sign}{delta:>7.1f}"
        )

    print(separator + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Elo updater…")

    # 1. Compute updated ratings
    updated = update_elos()

    # 2. Print diff report
    elo_diff_report()

    # 3. Save updated CSV
    save_updated_elos()
