import { useState } from "react";

// --- ELO DATA (eloratings.net, ene 2026) ---
const ELO_FULL = {
  "México": 1836, "Sudáfrica": 1640, "Corea del Sur": 1800, "Chequia": 1762,
  "Canadá": 1783, "Bosnia": 1700, "Qatar": 1610, "Suiza": 1897,
  "Brasil": 1979, "Marruecos": 1820, "Haití": 1450, "Escocia": 1760,
  "USA": 1818, "Paraguay": 1740, "Australia": 1768, "Turquía": 1880,
  "Alemania": 1910, "Curazao": 1380, "Países Bajos": 1959, "Japón": 1879,
  "España": 2171, "Cabo Verde": 1590, "Bélgica": 1849, "Egipto": 1680,
  "Arabia Saudita": 1680, "Uruguay": 1890, "Irán": 1730, "Nueva Zelanda": 1560,
  "Francia": 2063, "Albania": 1650, "Portugal": 1976, "Argentina": 2113,
  "Inglaterra": 2042, "Croacia": 1933, "Ghana": 1660, "Panamá": 1650,
  "Colombia": 1998, "Ecuador": 1933, "Senegal": 1869, "Uzbekistán": 1580,
  "Italia": 1859, "Congo DR": 1550, "Jordania": 1620, "Serbia": 1820,
  "Dinamarca": 1864, "Costa Rica": 1700, "Iraq": 1620,
};

const FIRST_MATCHES = [
  { date: "Jue 11 Jun", home: "México", away: "Sudáfrica", group: "A", host_boost: true },
  { date: "Jue 11 Jun", home: "Corea del Sur", away: "Chequia", group: "A" },
  { date: "Vie 12 Jun", home: "Canadá", away: "Bosnia", group: "B", host_boost: true },
  { date: "Vie 12 Jun", home: "USA", away: "Paraguay", group: "D", host_boost: true },
  { date: "Sáb 13 Jun", home: "Qatar", away: "Suiza", group: "B" },
  { date: "Sáb 13 Jun", home: "Brasil", away: "Marruecos", group: "C" },
  { date: "Sáb 13 Jun", home: "Haití", away: "Escocia", group: "C" },
  { date: "Dom 14 Jun", home: "Alemania", away: "Curazao", group: "E" },
  { date: "Dom 14 Jun", home: "Países Bajos", away: "Japón", group: "E" },
];

// SCORING SYSTEM: 3pts exact score, 1pt correct result, 6pts champion
const POINTS = { exact: 3, result: 1, champion: 6 };

// --- MODEL ---
function eloWinProb(rA, rB, boost = 0) {
  return 1 / (1 + Math.pow(10, -(rA - rB + boost) / 400));
}

function threeWayProbs(rHome, rAway, isHost = false) {
  const boost = isHost ? 100 : 60;
  const pHome = eloWinProb(rHome, rAway, boost);
  const eloDiff = Math.abs(rHome - rAway + boost);
  const pDraw = Math.min(0.28 * Math.exp(-Math.pow(eloDiff / 600, 1.5)), Math.min(pHome, 1 - pHome) * 0.85);
  return {
    home: Math.max(0.03, pHome - pDraw / 2),
    draw: Math.max(0.05, pDraw),
    away: Math.max(0.03, 1 - (pHome - pDraw / 2) - pDraw),
  };
}

function expectedGoals(rA, rB, boost = 60) {
  const dr = (rA - rB + boost) / 400;
  return {
    lambdaA: Math.max(0.3, 1.35 * (1 + 0.6 * dr)),
    lambdaB: Math.max(0.3, 1.35 * (1 - 0.6 * dr)),
  };
}

function factorial(n) { return n <= 1 ? 1 : n * factorial(n - 1); }
function poisson(lambda, k) { return (Math.pow(lambda, k) * Math.exp(-lambda)) / factorial(k); }

function scoreMatrix(lA, lB) {
  const m = [];
  for (let a = 0; a <= 5; a++)
    for (let b = 0; b <= 5; b++)
      m.push({ score: `${a}-${b}`, home: a, away: b, prob: poisson(lA, a) * poisson(lB, b) });
  return m.sort((x, y) => y.prob - x.prob);
}

// CORE: expected value of each decision under 3/1 scoring system
function expectedValues(scores, probs) {
  // EV of betting exact score (top score)
  const topScore = scores[0];
  const evExact = topScore.prob * POINTS.exact;

  // EV of betting result only
  const evHomeWin = probs.home * POINTS.result;
  const evDraw = probs.draw * POINTS.result;
  const evAwayWin = probs.away * POINTS.result;

  // Best result EV
  const bestResultEV = Math.max(evHomeWin, evDraw, evAwayWin);
  const bestResult = evHomeWin >= evDraw && evHomeWin >= evAwayWin ? "home"
    : evDraw >= evAwayWin ? "draw" : "away";

  // Threshold: exact score worth it if EV(exact) > EV(result)
  // But exact score also gives 1pt if right team wins (partial) — actually NO in this system
  // In this quiniela: exact = 3pts, result = 1pt, they're exclusive bets on score vs winner
  // Assume you bet ONE thing per match
  const preferExact = evExact > bestResultEV;

  return { evExact, evHomeWin, evDraw, evAwayWin, bestResultEV, bestResult, preferExact, topScore };
}

function consensusBias(homeTeam, probs) {
  const LATAM = ["México", "Brasil", "Argentina", "Colombia", "Uruguay", "Ecuador"];
  const FAMOUS = ["España", "Francia", "Alemania", "Países Bajos", "Inglaterra", "Portugal"];
  let bias = 0;
  if (LATAM.includes(homeTeam)) bias += 0.12;
  if (FAMOUS.includes(homeTeam)) bias += 0.08;
  const consensusHome = Math.min(0.92, probs.home + bias);
  return {
    consensusHome,
    edge: probs.home - consensusHome,
  };
}

// --- COLORS ---
const C = {
  bg: "#080810", surface: "#11111c", card: "#181826",
  border: "#252538", accent: "#7c6af5", accentLight: "#b0a6ff",
  gold: "#f0c040", green: "#4ade80", red: "#f87171",
  text: "#e8e8f4", muted: "#777799",
};

// --- COMPONENTS ---
function ProbBar({ pHome, pDraw, pAway, homeTeam, awayTeam }) {
  const fmt = v => (v * 100).toFixed(0) + "%";
  return (
    <div>
      <div style={{ display: "flex", borderRadius: 4, overflow: "hidden", height: 8, marginBottom: 6 }}>
        <div style={{ width: fmt(pHome), background: C.accent, transition: "width 0.4s" }} />
        <div style={{ width: fmt(pDraw), background: C.muted, transition: "width 0.4s" }} />
        <div style={{ width: fmt(pAway), background: C.red, transition: "width 0.4s" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
        <span style={{ color: C.accentLight }}>{homeTeam} {fmt(pHome)}</span>
        <span style={{ color: C.muted }}>Empate {fmt(pDraw)}</span>
        <span style={{ color: C.red }}>{awayTeam} {fmt(pAway)}</span>
      </div>
    </div>
  );
}

function EVPanel({ ev, scores, probs, homeName, awayName }) {
  const { evExact, evHomeWin, evDraw, evAwayWin, preferExact, topScore, bestResult } = ev;

  const decisionLabel = preferExact
    ? `Apostar marcador exacto: ${topScore.score}`
    : bestResult === "home" ? `Apostar victoria ${homeName}`
    : bestResult === "draw" ? "Apostar empate"
    : `Apostar victoria ${awayName}`;

  const decisionEV = preferExact ? evExact
    : bestResult === "home" ? evHomeWin
    : bestResult === "draw" ? evDraw : evAwayWin;

  const evRows = [
    { label: `Marcador exacto (${topScore.score})`, ev: evExact, pts: 3, prob: topScore.prob, highlight: preferExact },
    { label: `Victoria ${homeName}`, ev: evHomeWin, pts: 1, prob: probs.home, highlight: !preferExact && bestResult === "home" },
    { label: "Empate", ev: evDraw, pts: 1, prob: probs.draw, highlight: !preferExact && bestResult === "draw" },
    { label: `Victoria ${awayName}`, ev: evAwayWin, pts: 1, prob: probs.away, highlight: !preferExact && bestResult === "away" },
  ];

  return (
    <div style={{ marginTop: 14 }}>
      {/* Decision box */}
      <div style={{
        background: `linear-gradient(135deg, ${C.accent}22, ${C.accent}08)`,
        border: `1px solid ${C.accent}55`, borderRadius: 10, padding: "12px 16px", marginBottom: 12,
      }}>
        <div style={{ fontSize: 10, color: C.accent, fontWeight: 700, letterSpacing: 1.5, marginBottom: 4 }}>
          DECISIÓN ÓPTIMA · SISTEMA 3/1/6
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: C.text }}>{decisionLabel}</div>
        <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>
          Valor esperado: <span style={{ color: C.gold, fontWeight: 700 }}>{decisionEV.toFixed(3)} pts</span>
        </div>
      </div>

      {/* EV table */}
      <div style={{ fontSize: 11, color: C.muted, marginBottom: 6, letterSpacing: 1 }}>COMPARACIÓN DE VALOR ESPERADO</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {evRows.map((row, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 10,
            background: row.highlight ? `${C.accent}18` : C.surface,
            border: `1px solid ${row.highlight ? C.accent + "44" : C.border}`,
            borderRadius: 8, padding: "8px 12px",
          }}>
            <div style={{ flex: 1, fontSize: 12, color: row.highlight ? C.accentLight : C.muted }}>{row.label}</div>
            <div style={{ fontSize: 11, color: C.muted, width: 50, textAlign: "right" }}>
              {(row.prob * 100).toFixed(1)}%
            </div>
            <div style={{ fontSize: 11, color: C.muted, width: 30, textAlign: "right" }}>×{row.pts}pt</div>
            <div style={{
              fontSize: 13, fontWeight: 700, width: 50, textAlign: "right",
              color: row.highlight ? C.gold : C.muted,
            }}>
              {row.ev.toFixed(3)}
            </div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: C.muted, marginTop: 6, fontStyle: "italic" }}>
        EV = P(evento) × puntos. Máximo EV = decisión óptima.
      </div>
    </div>
  );
}

function MatchCard({ match, expanded, onToggle }) {
  const homeElo = ELO_FULL[match.home] || 1600;
  const awayElo = ELO_FULL[match.away] || 1600;
  const probs = threeWayProbs(homeElo, awayElo, match.host_boost);
  const { lambdaA, lambdaB } = expectedGoals(homeElo, awayElo, match.host_boost ? 100 : 60);
  const scores = scoreMatrix(lambdaA, lambdaB);
  const ev = expectedValues(scores, probs);
  const consensus = consensusBias(match.home, probs);
  const topScores = scores.slice(0, 6);

  const hasEdge = Math.abs(consensus.edge) > 0.05;
  const edgeDir = consensus.edge < 0;

  return (
    <div onClick={onToggle} style={{
      background: expanded ? C.card : C.surface,
      border: `1px solid ${expanded ? C.accent + "55" : C.border}`,
      borderRadius: 12, padding: "14px 18px", cursor: "pointer",
      transition: "all 0.2s", marginBottom: 10,
    }}>
      {/* Top row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 6 }}>
          <span style={{ fontSize: 10, color: C.muted, background: C.border, padding: "2px 7px", borderRadius: 8 }}>
            Grupo {match.group}
          </span>
          <span style={{ fontSize: 10, color: C.muted }}>{match.date}</span>
          {match.host_boost && (
            <span style={{ fontSize: 10, color: C.gold, background: "rgba(240,192,64,0.1)", padding: "2px 7px", borderRadius: 8 }}>
              🏠 Local
            </span>
          )}
        </div>
        {hasEdge && (
          <span style={{
            fontSize: 10, padding: "2px 8px", borderRadius: 10,
            background: edgeDir ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)",
            color: edgeDir ? C.green : C.red,
            border: `1px solid ${edgeDir ? C.green : C.red}44`,
          }}>
            {edgeDir ? "⚡ Upset tiene valor" : "⚠ Consenso inflado"} ({(Math.abs(consensus.edge) * 100).toFixed(0)}%)
          </span>
        )}
      </div>

      {/* Teams */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 17, fontWeight: 800, color: C.text }}>{match.home}</div>
          <div style={{ fontSize: 10, color: C.muted }}>Elo {homeElo}</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: C.muted, letterSpacing: 2 }}>VS</div>
          <div style={{ fontSize: 10, color: C.accent, marginTop: 2 }}>
            EV ópt: <span style={{ fontWeight: 700, color: C.gold }}>{Math.max(ev.evExact, ev.evHomeWin, ev.evDraw, ev.evAwayWin).toFixed(2)}</span>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 17, fontWeight: 800, color: C.text }}>{match.away}</div>
          <div style={{ fontSize: 10, color: C.muted }}>Elo {awayElo}</div>
        </div>
      </div>

      <ProbBar pHome={probs.home} pDraw={probs.draw} pAway={probs.away} homeTeam={match.home} awayTeam={match.away} />

      {expanded && (
        <div style={{ marginTop: 14, borderTop: `1px solid ${C.border}`, paddingTop: 14 }}>
          {/* xG row */}
          <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
            <div style={{ flex: 1, background: C.bg, borderRadius: 8, padding: "10px 12px" }}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 3 }}>Goles esperados (xG)</div>
              <div style={{ fontSize: 13, fontWeight: 700 }}>
                <span style={{ color: C.accentLight }}>{lambdaA.toFixed(2)}</span>
                <span style={{ color: C.muted }}> — </span>
                <span style={{ color: C.red }}>{lambdaB.toFixed(2)}</span>
              </div>
            </div>
            <div style={{ flex: 1, background: C.bg, borderRadius: 8, padding: "10px 12px" }}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 3 }}>Δ Elo</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.gold }}>
                {homeElo - awayElo > 0 ? "+" : ""}{homeElo - awayElo}
              </div>
            </div>
          </div>

          {/* Score grid */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 8, letterSpacing: 1 }}>MARCADORES MÁS PROBABLES</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
              {topScores.map((s, i) => (
                <div key={s.score} style={{
                  background: i === 0 ? `${C.accent}28` : C.bg,
                  border: `1px solid ${i === 0 ? C.accent : C.border}`,
                  borderRadius: 8, padding: "6px 12px", textAlign: "center", minWidth: 52,
                }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: i === 0 ? C.accentLight : C.text }}>{s.score}</div>
                  <div style={{ fontSize: 10, color: C.muted }}>{(s.prob * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </div>

          {/* EV Panel — the new core */}
          <EVPanel ev={ev} scores={scores} probs={probs} homeName={match.home} awayName={match.away} />

          {/* Consensus note */}
          <div style={{
            marginTop: 12, fontSize: 11, color: C.muted,
            background: C.bg, borderRadius: 8, padding: "8px 12px",
          }}>
            Consenso Avera estimado: <span style={{ color: C.text }}>{(consensus.consensusHome * 100).toFixed(0)}%</span> {match.home} ·
            Modelo: <span style={{ color: C.accentLight }}>{(probs.home * 100).toFixed(0)}%</span> {match.home}
          </div>
        </div>
      )}
    </div>
  );
}

function CustomMatch() {
  const teams = Object.keys(ELO_FULL).sort();
  const [home, setHome] = useState("España");
  const [away, setAway] = useState("Argentina");
  const [isHost, setIsHost] = useState(false);

  const homeElo = ELO_FULL[home] || 1700;
  const awayElo = ELO_FULL[away] || 1700;
  const probs = threeWayProbs(homeElo, awayElo, isHost);
  const { lambdaA, lambdaB } = expectedGoals(homeElo, awayElo, isHost ? 100 : 60);
  const scores = scoreMatrix(lambdaA, lambdaB);
  const ev = expectedValues(scores, probs);

  const sel = {
    background: C.bg, color: C.text, border: `1px solid ${C.border}`,
    borderRadius: 8, padding: "8px 12px", fontSize: 13, flex: 1, cursor: "pointer",
  };

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
      <div style={{ fontSize: 11, color: C.accent, fontWeight: 700, letterSpacing: 1.5, marginBottom: 14 }}>
        SIMULADOR PERSONALIZADO
      </div>
      <div style={{ display: "flex", gap: 10, marginBottom: 10, alignItems: "center" }}>
        <select value={home} onChange={e => setHome(e.target.value)} style={sel}>
          {teams.map(t => <option key={t}>{t}</option>)}
        </select>
        <span style={{ color: C.muted, fontWeight: 700, fontSize: 12 }}>VS</span>
        <select value={away} onChange={e => setAway(e.target.value)} style={sel}>
          {teams.map(t => <option key={t}>{t}</option>)}
        </select>
      </div>
      <label style={{ display: "flex", gap: 8, alignItems: "center", color: C.muted, fontSize: 12, marginBottom: 14, cursor: "pointer" }}>
        <input type="checkbox" checked={isHost} onChange={e => setIsHost(e.target.checked)} style={{ accentColor: C.accent }} />
        Anfitrión del torneo (+100 Elo boost)
      </label>

      <ProbBar pHome={probs.home} pDraw={probs.draw} pAway={probs.away} homeTeam={home} awayTeam={away} />

      <div style={{ display: "flex", gap: 10, margin: "12px 0" }}>
        <div style={{ flex: 1, background: C.bg, borderRadius: 8, padding: "10px 12px" }}>
          <div style={{ fontSize: 10, color: C.muted }}>xG</div>
          <div style={{ fontSize: 13, fontWeight: 700, marginTop: 2 }}>
            <span style={{ color: C.accentLight }}>{lambdaA.toFixed(2)}</span>
            <span style={{ color: C.muted }}> — </span>
            <span style={{ color: C.red }}>{lambdaB.toFixed(2)}</span>
          </div>
        </div>
        <div style={{ flex: 1, background: C.bg, borderRadius: 8, padding: "10px 12px" }}>
          <div style={{ fontSize: 10, color: C.muted }}>Δ Elo</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.gold, marginTop: 2 }}>{homeElo} — {awayElo}</div>
        </div>
      </div>

      <EVPanel ev={ev} scores={scores} probs={probs} homeName={home} awayName={away} />
    </div>
  );
}

// Champion EV tab
function ChampionTab() {
  const contenders = [
    { team: "España", elo: 2171, pWin: 0.19 },
    { team: "Argentina", elo: 2113, pWin: 0.16 },
    { team: "Francia", elo: 2063, pWin: 0.13 },
    { team: "Inglaterra", elo: 2042, pWin: 0.10 },
    { team: "Portugal", elo: 1976, pWin: 0.08 },
    { team: "Brasil", elo: 1979, pWin: 0.08 },
    { team: "Países Bajos", elo: 1959, pWin: 0.06 },
    { team: "Alemania", elo: 1910, pWin: 0.05 },
    { team: "Colombia", elo: 1998, pWin: 0.04 },
    { team: "Croacia", elo: 1933, pWin: 0.03 },
  ];

  // Consensus: what will Avera bet?
  const LATAM_INFLATED = ["Argentina", "Brasil", "Colombia"];
  const rows = contenders.map(c => {
    const consensusInflation = LATAM_INFLATED.includes(c.team) ? 1.4 : 1.0;
    const consensusP = Math.min(c.pWin * consensusInflation, 0.95);
    const evChampion = c.pWin * POINTS.champion;
    // Edge = model prob vs consensus — if consensus > model, less value (others will bet it)
    const edge = c.pWin - consensusP;
    return { ...c, consensusP, evChampion, edge };
  });

  return (
    <div>
      <div style={{
        background: `${C.accent}11`, border: `1px solid ${C.accent}33`,
        borderRadius: 10, padding: "12px 16px", marginBottom: 16,
      }}>
        <div style={{ fontSize: 10, color: C.accent, fontWeight: 700, letterSpacing: 1.5, marginBottom: 4 }}>
          JACKPOT — CAMPEÓN DEL MUNDIAL
        </div>
        <div style={{ fontSize: 13, color: C.text, lineHeight: 1.6 }}>
          6 puntos por acertar al campeón. Es el pronóstico con mayor impacto en el marcador final.
          La estrategia óptima: elegir el equipo donde <span style={{ color: C.gold }}>EV(modelo) &gt; EV(consenso)</span> — es decir,
          donde Avera subestima la probabilidad real.
        </div>
      </div>

      <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1, marginBottom: 8 }}>
        EQUIPOS FAVORITOS · EV = P(campeón) × 6 pts
      </div>

      {rows.map((r, i) => {
        const isValue = r.edge > 0;
        return (
          <div key={r.team} style={{
            display: "flex", alignItems: "center", gap: 10,
            background: i === 0 ? `${C.gold}10` : C.surface,
            border: `1px solid ${i === 0 ? C.gold + "44" : C.border}`,
            borderRadius: 10, padding: "10px 14px", marginBottom: 7,
          }}>
            <div style={{ fontSize: 13, color: C.muted, width: 20 }}>#{i + 1}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>{r.team}</div>
              <div style={{ fontSize: 10, color: C.muted }}>Elo {r.elo}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 12, color: C.muted }}>P: <span style={{ color: C.accentLight }}>{(r.pWin * 100).toFixed(0)}%</span></div>
              <div style={{ fontSize: 11, color: C.muted }}>EV: <span style={{ color: C.gold, fontWeight: 700 }}>{r.evChampion.toFixed(2)}</span></div>
            </div>
            <div style={{ textAlign: "right", minWidth: 80 }}>
              <span style={{
                fontSize: 10, padding: "3px 8px", borderRadius: 8,
                background: isValue ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)",
                color: isValue ? C.green : C.red,
                border: `1px solid ${isValue ? C.green : C.red}33`,
              }}>
                {isValue ? "✓ Value" : "✗ Sobrevalorado"}
              </span>
            </div>
          </div>
        );
      })}

      <div style={{ fontSize: 10, color: C.muted, marginTop: 10, fontStyle: "italic", lineHeight: 1.6 }}>
        "Value" = el modelo le da más probabilidad de la que el consenso de Avera probablemente le asignará.
        Argentina y Brasil tienen alto EV absoluto pero el sesgo LATAM los infla en quinielas corporativas mexicanas.
        España es el pick de mayor EV ajustado por consenso.
      </div>
    </div>
  );
}

export default function App() {
  const [expanded, setExpanded] = useState(null);
  const [tab, setTab] = useState("fixtures");

  return (
    <div style={{
      minHeight: "100vh", background: C.bg, color: C.text,
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
      padding: "24px 16px", maxWidth: 680, margin: "0 auto",
    }}>
      <div style={{ marginBottom: 26 }}>
        <div style={{ fontSize: 10, letterSpacing: 3, color: C.accent, marginBottom: 5, textTransform: "uppercase" }}>
          Quiniela Intelligence System · Avera 2026
        </div>
        <h1 style={{
          fontSize: 26, fontWeight: 900, margin: 0, lineHeight: 1.1,
          background: `linear-gradient(135deg, ${C.text}, ${C.accentLight})`,
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
        }}>
          Mundial 2026
        </h1>
        <p style={{ color: C.muted, fontSize: 12, marginTop: 5 }}>
          Elo + Poisson · Sistema 3 pts exacto / 1 pt resultado / 6 pts campeón
        </p>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {[["fixtures", "Semana 1"], ["simulator", "Simulador"], ["champion", "Campeón"]].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} style={{
            padding: "7px 16px", borderRadius: 18, border: "none", cursor: "pointer",
            fontSize: 12, fontWeight: 600, transition: "all 0.2s",
            background: tab === key ? C.accent : C.surface,
            color: tab === key ? "#fff" : C.muted,
          }}>{label}</button>
        ))}
      </div>

      {tab === "fixtures" && (
        <div>
          <div style={{ fontSize: 10, color: C.muted, marginBottom: 10, letterSpacing: 1 }}>
            TOCA UN PARTIDO PARA VER ANÁLISIS COMPLETO + DECISIÓN ÓPTIMA
          </div>
          {FIRST_MATCHES.map((m, i) => (
            <MatchCard key={i} match={m} expanded={expanded === i}
              onToggle={() => setExpanded(expanded === i ? null : i)} />
          ))}
        </div>
      )}

      {tab === "simulator" && <CustomMatch />}
      {tab === "champion" && <ChampionTab />}

      <div style={{
        marginTop: 22, padding: "10px 14px", background: C.surface,
        borderRadius: 8, border: `1px solid ${C.border}`,
        fontSize: 10, color: C.muted, lineHeight: 1.8,
      }}>
        <span style={{ color: C.accent, fontWeight: 700 }}>METODOLOGÍA · </span>
        Elo: eloratings.net ene 2026. Distribución de goles: Poisson bivariado con λ calibrado por diferencia Elo.
        Localía: +60 Elo estándar, +100 anfitrión. EV calculado bajo sistema Prodemaster: 3pts marcador exacto, 1pt resultado, 6pts campeón.
        Sesgo consenso: +12% LATAM, +8% potencias europeas históricas.
      </div>
    </div>
  );
}
