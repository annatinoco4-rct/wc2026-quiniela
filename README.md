# ⚽ wc2026-quiniela

Winning a prediction pool isn't about predicting outcomes correctly. It's about outperforming predictably irrational competitors.

**Quantitative strategy for winning a corporate World Cup pool — using Elo ratings, Poisson models, Monte Carlo simulation, and game theory.**

This is not a football fan project. It's a decision-making problem under uncertainty with 101 irrational competitors.

---

## The core insight

Winning a quiniela (prediction pool) is not the same as predicting match outcomes correctly. It requires **outperforming predictably irrational competitors** — exploiting their biases (LATAM favoritism, narrative-driven picks, recency bias) to find positive expected value bets they systematically miss.

---

## Scoring system (Prodemaster)

| Event | Points |
|---|---|
| Exact scoreline | 3 pts |
| Correct result (W/D/L) | 1 pt |
| Correct champion | 6 pts |

This asymmetry drives the whole strategy: maximize EV under a 3/1/6 system, not raw accuracy.

---

## Project structure

```
wc2026-quiniela/
│
├── data/
│   ├── elo_ratings.csv         # Pre-tournament Elo ratings (eloratings.net)
│   ├── fixtures.csv            # Full tournament schedule
│   └── results.csv             # Actual results (updated live)
│
├── notebooks/
│   ├── 01_elo_model.ipynb      # Elo ratings + win probability model
│   ├── 02_poisson_model.ipynb  # Score distribution via bivariate Poisson
│   ├── 03_monte_carlo.ipynb    # Full tournament simulation (10k runs)
│   └── 04_game_theory.ipynb   # Quiniela strategy vs competitor consensus
│
├── src/
│   ├── model.py                # Elo + Poisson core, importable
│   ├── simulator.py            # Monte Carlo tournament simulator
│   └── strategy.py             # Game theory + EV optimization
│
├── dashboard/
│   └── app.jsx                 # Interactive prediction dashboard (React)
│
└── picks/
    └── my_picks.json           # Live picks + running score tracker
```

---

## Methodology

### Layer 1 — Elo ratings
Each team gets a numerical strength rating updated after every match. Win probability between two teams is derived from their Elo difference using the standard formula:

$$P(A \text{ wins}) = \frac{1}{1 + 10^{-(R_A - R_B + \text{boost})/400}}$$

Home/host boost: +60 Elo standard, +100 for tournament hosts (MEX/USA/CAN).

### Layer 2 — Bivariate Poisson model
Expected goals (λ) for each team are derived from Elo difference and calibrated to historical World Cup scoring averages (~1.35 goals/team/match). Score probabilities follow:

$$P(A=a, B=b) = \text{Poisson}(\lambda_A, a) \times \text{Poisson}(\lambda_B, b)$$

### Layer 3 — Expected value under 3/1/6 system
For each match, we compute EV for every possible bet:

$$EV(\text{exact score}) = P(\text{score}) \times 3$$
$$EV(\text{result}) = P(\text{result}) \times 1$$

Optimal pick = $\arg\max EV$.

### Layer 4 — Game theory adjustment
Competitor consensus is modeled with empirical biases:
- +12% inflation for LATAM teams (MEX, BRA, ARG, COL, URU, ECU) in a Mexican corporate pool
- +8% inflation for globally famous European clubs (ESP, FRA, GER, NED, ENG, POR)

Edge = Model probability − Consensus probability. Positive edge = contrarian value.

---

## Live results tracker

| Match | My pick | Result | Points |
|---|---|---|---|
| MEX vs RSA | 2-0 ✓ | 2-0 | **3** |
| KOR vs CZE | 1-0 ✗ | 2-1 | 1 |
| ... | | | |

**Running total: 4 pts**

---

## Requirements

```
python >= 3.10
numpy
pandas
scipy
matplotlib
seaborn
jupyter
```

```bash
pip install -r requirements.txt
```

---

## Data sources

- **Elo ratings**: [eloratings.net](https://eloratings.net)
- **Fixtures & results**: FIFA official / football-data.org
- **Odds reference**: FanDuel, Kalshi prediction markets

---

*Built during the 2026 World Cup. Model predictions vs actual results documented in real time.*
