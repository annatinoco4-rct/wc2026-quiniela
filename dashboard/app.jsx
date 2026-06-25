import { useState } from "react";

// Updated Elos post-tournament recalibration
const ELO = {
  "México": 1857, "Sudáfrica": 1653, "Corea del Sur": 1786, "Chequia": 1743,
  "Canadá": 1779, "Bosnia": 1705, "Qatar": 1604, "Suiza": 1902,
  "Brasil": 1980, "Marruecos": 1835, "Haití": 1444, "Escocia": 1750,
  "USA": 1835, "Paraguay": 1746, "Australia": 1772, "Turquía": 1853,
  "Alemania": 1911, "Curazao": 1388, "Países Bajos": 1957, "Japón": 1881,
  "España": 2163, "Cabo Verde": 1606, "Bélgica": 1841, "Egipto": 1691,
  "Arabia Saudita": 1684, "Uruguay": 1878, "Irán": 1729, "Nueva Zelanda": 1558,
  "Francia": 2069, "Albania": 1650, "Portugal": 1970, "Argentina": 2113,
  "Inglaterra": 2041, "Croacia": 1929, "Ghana": 1678, "Panamá": 1637,
  "Colombia": 2001, "Ecuador": 1924, "Senegal": 1864, "Uzbekistán": 1576,
  "Italia": 1859, "Congo DR": 1557, "Jordania": 1620, "Serbia": 1820,
  "Dinamarca": 1864, "Costa Rica": 1700, "Iraq": 1619, "Noruega": 1940,
  "Suecia": 1870, "Túnez": 1700, "Costa de Marfil": 1800, "Argelia": 1730,
  "Austria": 1860,
};

const LAMBDA_BASE = 1.20;
const DRAW_BOOST = 1.10;
const LATAM = new Set(["México","Brasil","Argentina","Colombia","Uruguay","Ecuador"]);
const FAMOUS_EU = new Set(["España","Francia","Alemania","Países Bajos","Inglaterra","Portugal"]);

const R3_MATCHES = [
  // JUE 25 JUN — picks con EV calculado
  { date: "Jun 25", home: "Curazao", away: "Costa de Marfil", group: "E", pick: "0-1", ev: 1.173, top: [["0-1","16.8%"],["0-2","15.5%"],["0-3","9.5%"]], pending: true },
  { date: "Jun 25", home: "Ecuador", away: "Alemania", group: "E", pick: "1-1", ev: 0.716, top: [["1-1","12.9%"],["1-0","12.2%"],["0-1","9.5%"]], pending: true },
  { date: "Jun 25", home: "Japón", away: "Suecia", group: "F", pick: "1-1", ev: 0.690, top: [["1-1","12.9%"],["1-0","12.0%"],["0-1","9.8%"]], pending: true },
  { date: "Jun 25", home: "Túnez", away: "Países Bajos", group: "F", pick: "0-1", ev: 0.933, top: [["0-1","14.1%"],["1-1","11.9%"],["0-2","11.0%"]], pending: true },
  { date: "Jun 25", home: "Turquía", away: "USA", group: "D", pick: "1-1", ev: 0.707, top: [["1-1","12.9%"],["1-0","12.2%"],["0-1","9.6%"]], pending: true },
  { date: "Jun 25", home: "Paraguay", away: "Australia", group: "D", pick: "1-1", ev: 0.626, top: [["1-1","13.0%"],["1-0","11.4%"],["0-1","10.3%"]], pending: true },
  // VIE 26 JUN
  { date: "Jun 26", home: "Noruega", away: "Francia", group: "I", pick: "0-1", ev: 0.690, top: [["1-1","12.9%"],["0-1","12.0%"],["1-0","9.8%"]], pending: true, champion_pick: true },
  { date: "Jun 26", home: "Senegal", away: "Iraq", group: "I", pick: "1-0", ev: 1.104, top: [["1-0","15.9%"],["2-0","13.9%"],["1-1","10.3%"]], pending: true },
  { date: "Jun 26", home: "Nueva Zelanda", away: "Bélgica", group: "G", pick: "0-1", ev: 0.976, top: [["0-1","14.5%"],["0-2","11.6%"],["1-1","11.6%"]], pending: true },
  { date: "Jun 26", home: "Egipto", away: "Irán", group: "G", pick: "1-1", ev: 0.604, top: [["1-1","13.0%"],["1-0","11.2%"],["0-1","10.5%"]], pending: true },
  { date: "Jun 26", home: "Cabo Verde", away: "Arabia Saudita", group: "H", pick: "1-1", ev: 0.596, top: [["1-1","13.1%"],["0-1","11.2%"],["1-0","10.6%"]], pending: true },
  { date: "Jun 26", home: "España", away: "Uruguay", group: "H", pick: "2-0", ev: 0.720, top: [["1-0","13.5%"],["2-0","11.8%"],["1-1","11.2%"]], pending: true },
  // SAB 27 JUN
  { date: "Jun 27", home: "Colombia", away: "Portugal", group: "K", pick: "1-0", ev: 0.730, top: [["1-1","12.8%"],["1-0","12.4%"],["0-1","9.4%"]], pending: true },
  { date: "Jun 27", home: "Congo DR", away: "Uzbekistán", group: "K", pick: "1-0", ev: 0.639, top: [["1-1","13.0%"],["1-0","11.6%"],["0-1","10.2%"]], pending: true },
  { date: "Jun 27", home: "Ghana", away: "Croacia", group: "L", pick: "0-1", ev: 0.918, top: [["0-1","14.0%"],["1-1","12.0%"],["0-2","10.8%"]], pending: true },
  { date: "Jun 27", home: "Dinamarca", away: "Serbia", group: "L", pick: "1-0", ev: 0.754, top: [["1-1","12.7%"],["1-0","12.6%"],["0-1","9.2%"]], pending: true },
  // DOM 28 JUN
  { date: "Jun 28", home: "Argelia", away: "Austria", group: "J", pick: "0-1", ev: 0.692, top: [["1-1","12.9%"],["0-1","12.0%"],["1-0","9.7%"]], pending: true },
  { date: "Jun 28", home: "Jordania", away: "Argentina", group: "J", pick: "0-1", ev: 1.248, top: [["0-1","18.0%"],["0-2","17.8%"],["0-3","11.7%"]], pending: true },
];

// MODEL (for probability bars)
function eloWinProb(rA, rB, boost=0) {
  return 1/(1+Math.pow(10,-(rA-rB+boost)/400));
}

function threeWay(rH, rA, host=false) {
  const boost = host ? 100 : 60;
  const pH = eloWinProb(rH, rA, boost);
  const diff = Math.abs(rH-rA+boost);
  const pD = Math.min(0.28*Math.exp(-Math.pow(diff/600, 1.5))*DRAW_BOOST, Math.min(pH,1-pH)*0.90);
  const pW = Math.max(0.03, pH-pD/2);
  const pL = Math.max(0.03, 1-pW-pD);
  const t = pW+Math.max(0.05,pD)+pL;
  return {home:pW/t, draw:Math.max(0.05,pD)/t, away:pL/t};
}

const C = {
  bg:"#080810",surface:"#11111c",card:"#181826",border:"#252538",
  accent:"#7c6af5",accentLight:"#b0a6ff",gold:"#f0c040",
  green:"#4ade80",red:"#f87171",orange:"#fb923c",text:"#e8e8f4",muted:"#777799",
};

function ProbBar({pHome,pDraw,pAway,homeTeam,awayTeam}) {
  const f=v=>(v*100).toFixed(0)+"%";
  return (
    <div>
      <div style={{display:"flex",borderRadius:4,overflow:"hidden",height:8,marginBottom:6}}>
        <div style={{width:f(pHome),background:C.accent}}/>
        <div style={{width:f(pDraw),background:C.muted}}/>
        <div style={{width:f(pAway),background:C.red}}/>
      </div>
      <div style={{display:"flex",justifyContent:"space-between",fontSize:11}}>
        <span style={{color:C.accentLight}}>{homeTeam} {f(pHome)}</span>
        <span style={{color:C.muted}}>Empate {f(pDraw)}</span>
        <span style={{color:C.red}}>{awayTeam} {f(pAway)}</span>
      </div>
    </div>
  );
}

function MatchCard({match, expanded, onToggle}) {
  const rH = ELO[match.home]||1650;
  const rA = ELO[match.away]||1650;
  const probs = threeWay(rH, rA);

  return (
    <div onClick={onToggle} style={{
      background:expanded?C.card:C.surface,
      border:`1px solid ${expanded?C.accent+"55":C.border}`,
      borderRadius:12, padding:"13px 16px", cursor:"pointer",
      transition:"all 0.2s", marginBottom:8,
    }}>
      {/* Header */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:9}}>
        <div style={{display:"flex",gap:5}}>
          <span style={{fontSize:10,color:C.muted,background:C.border,padding:"2px 7px",borderRadius:8}}>G{match.group}</span>
          <span style={{fontSize:10,color:C.muted}}>{match.date}</span>
          {match.champion_pick&&<span style={{fontSize:10,color:C.gold,background:"rgba(240,192,64,0.15)",padding:"2px 7px",borderRadius:8}}>⭐ Campeona</span>}
        </div>
        <div style={{display:"flex",gap:6,alignItems:"center"}}>
          <span style={{fontSize:11,padding:"2px 8px",borderRadius:10,fontWeight:700,background:`${C.orange}18`,color:C.orange,border:`1px solid ${C.orange}44`}}>
            Pick: {match.pick}
          </span>
          <span style={{fontSize:11,padding:"2px 8px",borderRadius:10,fontWeight:700,background:`${C.gold}18`,color:C.gold,border:`1px solid ${C.gold}44`}}>
            EV {match.ev.toFixed(3)}
          </span>
        </div>
      </div>

      {/* Teams */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:11}}>
        <div>
          <div style={{fontSize:16,fontWeight:800,color:C.text}}>{match.home}</div>
          <div style={{fontSize:10,color:C.muted}}>Elo {rH}</div>
        </div>
        <div style={{textAlign:"center",fontSize:11,color:C.muted,letterSpacing:2}}>VS</div>
        <div style={{textAlign:"right"}}>
          <div style={{fontSize:16,fontWeight:800,color:C.text}}>{match.away}</div>
          <div style={{fontSize:10,color:C.muted}}>Elo {rA}</div>
        </div>
      </div>

      <ProbBar pHome={probs.home} pDraw={probs.draw} pAway={probs.away} homeTeam={match.home} awayTeam={match.away}/>

      {expanded && (
        <div style={{marginTop:14,borderTop:`1px solid ${C.border}`,paddingTop:14}}>
          {/* Top scores */}
          <div style={{marginBottom:12}}>
            <div style={{fontSize:10,color:C.muted,letterSpacing:1,marginBottom:8}}>TOP MARCADORES + EV CALCULADO</div>
            <div style={{display:"flex",flexDirection:"column",gap:6}}>
              {match.top.map(([score, prob], i) => {
                // Calculate which result this score implies
                const [h,a] = score.split("-").map(Number);
                const impliedResult = h>a?"local gana":h===a?"empate":"visitante gana";
                const isOptimal = score === match.pick;
                return (
                  <div key={score} style={{
                    display:"flex",alignItems:"center",gap:10,
                    background:isOptimal?`${C.accent}18`:C.bg,
                    border:`1px solid ${isOptimal?C.accent+"55":C.border}`,
                    borderRadius:8,padding:"8px 12px",
                  }}>
                    <div style={{fontSize:16,fontWeight:800,color:isOptimal?C.accentLight:C.text,width:40}}>{score}</div>
                    <div style={{flex:1,fontSize:11,color:C.muted}}>{impliedResult}</div>
                    <div style={{fontSize:12,color:isOptimal?C.gold:C.muted,fontWeight:isOptimal?700:400}}>{prob}</div>
                    {isOptimal&&<div style={{fontSize:10,color:C.accent,fontWeight:700}}>← ÓPTIMO</div>}
                  </div>
                );
              })}
            </div>
          </div>

          {/* EV explanation */}
          <div style={{background:C.bg,borderRadius:8,padding:"10px 12px",fontSize:11,color:C.muted,lineHeight:1.7}}>
            <span style={{color:C.text,fontWeight:600}}>EV {match.ev.toFixed(3)} pts</span> = P(exacto)×3 + P(resultado no exacto)×1<br/>
            <span style={{color:C.muted}}>Δ Elo: {rH>rA?"+":""}{rH-rA} · P(empate recalibrado): {(probs.draw*100).toFixed(0)}%</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [expanded, setExpanded] = useState(null);
  const [tab, setTab] = useState("thu");

  const byDate = {
    thu: R3_MATCHES.filter(m=>m.date==="Jun 25"),
    fri: R3_MATCHES.filter(m=>m.date==="Jun 26"),
    sat: R3_MATCHES.filter(m=>m.date==="Jun 27"),
    sun: R3_MATCHES.filter(m=>m.date==="Jun 28"),
  };

  const tabs = [
    ["thu","Jue 25 (6)"],
    ["fri","Vie 26 (6)"],
    ["sat","Sáb 27 (4)"],
    ["sun","Dom 28 (2)"],
  ];

  return (
    <div style={{minHeight:"100vh",background:C.bg,color:C.text,fontFamily:"'DM Sans','Segoe UI',sans-serif",padding:"22px 14px",maxWidth:660,margin:"0 auto"}}>
      {/* Header */}
      <div style={{marginBottom:20}}>
        <div style={{fontSize:10,letterSpacing:3,color:C.accent,marginBottom:4,textTransform:"uppercase"}}>
          Round 3 · Picks con EV calculado
        </div>
        <h1 style={{fontSize:24,fontWeight:900,margin:0,background:`linear-gradient(135deg,${C.text},${C.accentLight})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>
          Mundial 2026
        </h1>
        <p style={{color:C.muted,fontSize:11,marginTop:4}}>
          Elos recalibrados post-R1+R2 · λ=1.20 · P(draw)×1.10
        </p>

        {/* Key insight */}
        <div style={{marginTop:12,background:`${C.orange}12`,border:`1px solid ${C.orange}33`,borderRadius:10,padding:"10px 14px"}}>
          <div style={{fontSize:10,color:C.orange,fontWeight:700,letterSpacing:1,marginBottom:4}}>INSIGHT CLAVE ROUND 3</div>
          <div style={{fontSize:12,color:C.text,lineHeight:1.6}}>
            En partidos muy parejos, el 1-1 tiene mayor P(exacto) ~13% pero <span style={{color:C.gold}}>menor EV</span> que apostar por el favorito con un marcador como 1-0 (~12%). Esto es porque el EV incluye el 1pt de "resultado correcto" — apostar por el ganador correcto aunque no aciertes el exacto suma más en promedio.
          </div>
        </div>

        <div style={{display:"flex",gap:7,marginTop:12}}>
          {[
            {label:"Posición",value:"#1",color:C.gold},
            {label:"Pts acum.",value:"~39",color:C.accentLight},
            {label:"Campeona",value:"🇫🇷",color:C.gold},
            {label:"Pendientes R3",value:"18",color:C.orange},
          ].map(s=>(
            <div key={s.label} style={{flex:1,background:C.surface,border:`1px solid ${C.border}`,borderRadius:9,padding:"7px 4px",textAlign:"center"}}>
              <div style={{fontSize:16,fontWeight:900,color:s.color}}>{s.value}</div>
              <div style={{fontSize:8,color:C.muted,marginTop:1}}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div style={{display:"flex",gap:6,marginBottom:16,flexWrap:"wrap"}}>
        {tabs.map(([key,label])=>(
          <button key={key} onClick={()=>setTab(key)} style={{
            padding:"7px 12px",borderRadius:18,border:"none",cursor:"pointer",
            fontSize:11,fontWeight:600,transition:"all 0.2s",
            background:tab===key?C.accent:C.surface,color:tab===key?"#fff":C.muted,
          }}>{label}</button>
        ))}
      </div>

      {/* Matches */}
      {(byDate[tab]||[]).map((m,i)=>{
        const key=`${tab}-${i}`;
        return <MatchCard key={key} match={m} expanded={expanded===key} onToggle={()=>setExpanded(expanded===key?null:key)}/>;
      })}

      <div style={{marginTop:20,padding:"9px 13px",background:C.surface,borderRadius:8,border:`1px solid ${C.border}`,fontSize:10,color:C.muted,lineHeight:1.8}}>
        <span style={{color:C.accent,fontWeight:700}}>METODOLOGÍA R3 · </span>
        Elos actualizados con resultados reales (K=20 grupos). λ=1.20 recalibrado post-R1.
        EV = P(exacto)×3 + P(resultado no exacto)×1. Pick óptimo = argmax(EV) sobre todos los marcadores posibles.
      </div>
    </div>
  );
}
