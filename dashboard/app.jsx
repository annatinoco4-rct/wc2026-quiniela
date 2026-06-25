import { useState } from "react";

const ELO = {
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
  "Dinamarca": 1864, "Costa Rica": 1700, "Iraq": 1620, "Noruega": 1940,
  "Suecia": 1870, "Túnez": 1700, "Costa de Marfil": 1800, "Argelia": 1730,
  "Austria": 1860,
};

const LAMBDA_BASE = 1.20;
const DRAW_BOOST_R2 = 1.10;
const LATAM = new Set(["México","Brasil","Argentina","Colombia","Uruguay","Ecuador"]);
const FAMOUS_EU = new Set(["España","Francia","Alemania","Países Bajos","Inglaterra","Portugal"]);

// ALL MATCHES — R1 played, R2 with picks hardcoded
const R1 = [
  { date: "Jun 11", home: "México", away: "Sudáfrica", group: "A", result: "2-0", pick: "2-0", pts: 3 },
  { date: "Jun 11", home: "Corea del Sur", away: "Chequia", group: "A", result: "2-1", pick: "1-0", pts: 1 },
  { date: "Jun 12", home: "Canadá", away: "Bosnia", group: "B", result: "1-1", pick: "2-0", pts: 0 },
  { date: "Jun 12", home: "USA", away: "Paraguay", group: "D", result: "4-1", pick: "2-1", pts: 1 },
  { date: "Jun 13", home: "Qatar", away: "Suiza", group: "B", result: "1-1", pick: "0-2", pts: 0 },
  { date: "Jun 13", home: "Brasil", away: "Marruecos", group: "C", result: "1-1", pick: "2-0", pts: 0 },
  { date: "Jun 13", home: "Haití", away: "Escocia", group: "C", result: "0-1", pick: "0-2", pts: 1 },
  { date: "Jun 13", home: "Australia", away: "Turquía", group: "D", result: "2-0", pick: "1-2", pts: 0 },
  { date: "Jun 14", home: "Alemania", away: "Curazao", group: "E", result: "7-1", pick: "4-0", pts: 1 },
  { date: "Jun 14", home: "Países Bajos", away: "Japón", group: "F", result: "2-2", pick: "2-1", pts: 0 },
  { date: "Jun 14", home: "Costa de Marfil", away: "Ecuador", group: "E", result: "1-0", pick: "1-0", pts: 3 },
  { date: "Jun 14", home: "Suecia", away: "Túnez", group: "F", result: "5-1", pick: "2-1", pts: 1 },
  { date: "Jun 15", home: "España", away: "Cabo Verde", group: "H", result: "0-0", pick: "2-0", pts: 0 },
  { date: "Jun 15", home: "Bélgica", away: "Egipto", group: "G", result: "1-1", pick: "2-0", pts: 0 },
  { date: "Jun 15", home: "Arabia Saudita", away: "Uruguay", group: "H", result: "1-1", pick: "1-1", pts: 3 },
  { date: "Jun 15", home: "Irán", away: "Nueva Zelanda", group: "G", result: "2-2", pick: "1-0", pts: 0 },
  { date: "Jun 16", home: "Francia", away: "Senegal", group: "I", result: "3-1", pick: "3-1", pts: 3, champion_pick: true },
  { date: "Jun 16", home: "Iraq", away: "Noruega", group: "I", result: "1-4", pick: "0-1", pts: 1 },
  { date: "Jun 16", home: "Argentina", away: "Argelia", group: "J", result: "3-0", pick: "2-0", pts: 1 },
  { date: "Jun 16", home: "Austria", away: "Jordania", group: "J", result: "3-1", pick: "1-0", pts: 1 },
  { date: "Jun 17", home: "Portugal", away: "Congo DR", group: "K", result: "1-1", pick: "2-0", pts: 0 },
  { date: "Jun 17", home: "Inglaterra", away: "Croacia", group: "L", result: "4-2", pick: "2-1", pts: 1 },
  { date: "Jun 17", home: "Ghana", away: "Panamá", group: "L", result: "1-0", pick: "1-1", pts: 0 },
  { date: "Jun 17", home: "Uzbekistán", away: "Colombia", group: "K", result: "1-3", pick: "0-2", pts: 1 },
];

const R2 = [
  // JUGADOS
  { date: "Jun 18", home: "Chequia", away: "Sudáfrica", group: "A", result: "1-1", pick: "2-1", pts: 0 },
  { date: "Jun 18", home: "Suiza", away: "Bosnia", group: "B", result: "4-1", pick: "2-0", pts: 1 },
  { date: "Jun 18", home: "Canadá", away: "Qatar", group: "B", result: "6-0", pick: "2-1", pts: 1 },
  { date: "Jun 18", home: "México", away: "Corea del Sur", group: "A", result: "1-0", pick: "2-1", pts: 1 },
  { date: "Jun 19", home: "USA", away: "Australia", group: "D", result: "2-1", pick: "2-1", pts: 3 },
  { date: "Jun 19", home: "Escocia", away: "Marruecos", group: "C", result: "1-1", pick: "1-1", pts: 3 },
  { date: "Jun 19", home: "Brasil", away: "Haití", group: "C", result: "3-0", pick: "3-0", pts: 3 },
  { date: "Jun 19", home: "Turquía", away: "Paraguay", group: "D", result: null, pick: "2-1", pending: true },
  // SAB 20 — con picks hardcodeados
  { date: "Jun 20", home: "Países Bajos", away: "Suecia", group: "F", result: null, pick: "1-0", pending: true },
  { date: "Jun 20", home: "Alemania", away: "Costa de Marfil", group: "E", result: null, pick: "2-1", pending: true },
  { date: "Jun 20", home: "Ecuador", away: "Curazao", group: "E", result: null, pick: "3-0", pending: true },
  { date: "Jun 20", home: "Japón", away: "Túnez", group: "F", result: null, pick: "2-0", pending: true },
  // DOM 21
  { date: "Jun 21", home: "España", away: "Arabia Saudita", group: "H", result: null, pick: "2-0", pending: true },
  { date: "Jun 21", home: "Bélgica", away: "Irán", group: "G", result: null, pick: "2-1", pending: true },
  { date: "Jun 21", home: "Uruguay", away: "Cabo Verde", group: "H", result: null, pick: "2-0", pending: true },
  { date: "Jun 21", home: "Nueva Zelanda", away: "Egipto", group: "G", result: null, pick: "1-1", pending: true },
  { date: "Jun 21", home: "Argentina", away: "Austria", group: "J", result: null, pick: "2-0", pending: true },
  { date: "Jun 21", home: "Colombia", away: "Senegal", group: "I", result: null, pick: "2-0", pending: true },
  // LUN 22
  { date: "Jun 22", home: "Francia", away: "Iraq", group: "I", result: null, pick: "3-0", pending: true, champion_pick: true },
  { date: "Jun 22", home: "Portugal", away: "Serbia", group: "K", result: null, pick: "2-1", pending: true },
  { date: "Jun 22", home: "Noruega", away: "Argelia", group: "J", result: null, pick: "2-0", pending: true },
  // MAR 23
  { date: "Jun 23", home: "Croacia", away: "Dinamarca", group: "L", result: null, pick: "1-1", pending: true },
  { date: "Jun 23", home: "Inglaterra", away: "Irán", group: "K", result: null, pick: "2-0", pending: true },
  { date: "Jun 23", home: "Egipto", away: "Uruguay", group: "G", result: null, pick: "0-2", pending: true },
];

// MODEL
function eloWinProb(rA, rB, boost = 0) {
  return 1 / (1 + Math.pow(10, -(rA - rB + boost) / 400));
}

function threeWay(rHome, rAway, isHost = false) {
  const boost = isHost ? 100 : 60;
  const pH = eloWinProb(rHome, rAway, boost);
  const diff = Math.abs(rHome - rAway + boost);
  const pD = Math.min(0.28 * Math.exp(-Math.pow(diff/600, 1.5)) * DRAW_BOOST_R2, Math.min(pH, 1-pH) * 0.90);
  const pW = Math.max(0.03, pH - pD/2);
  const pL = Math.max(0.03, 1 - pW - pD);
  const t = pW + Math.max(0.05,pD) + pL;
  return { home: pW/t, draw: Math.max(0.05,pD)/t, away: pL/t };
}

function xg(rA, rB, boost=60) {
  const dr = (rA - rB + boost)/400;
  return { lA: Math.max(0.3, LAMBDA_BASE*(1+0.6*dr)), lB: Math.max(0.3, LAMBDA_BASE*(1-0.6*dr)) };
}

function poisson(lam, k) { let r=Math.exp(-lam); for(let i=1;i<=k;i++) r*=lam/i; return r; }

function scoreMatrix(lA, lB) {
  const m=[];
  for(let a=0;a<=5;a++) for(let b=0;b<=5;b++) m.push({score:`${a}-${b}`,h:a,a:b,p:poisson(lA,a)*poisson(lB,b)});
  return m.sort((x,y)=>y.p-x.p);
}

function evForScore(s, probs) {
  const pEx=s.p;
  let pRes=s.h>s.a?probs.home:s.h===s.a?probs.draw:probs.away;
  return pEx*3+Math.max(0,pRes-pEx)*1;
}

function bestPick(scoreList, probs) {
  let best=null,bestEV=-1;
  for(const s of scoreList){const ev=evForScore(s,probs);if(ev>bestEV){bestEV=ev;best=s;}}
  return {score:best.score,ev:bestEV,prob:best.p};
}

function consensusBias(homeTeam, probs) {
  let bias=0;
  if(LATAM.has(homeTeam)) bias+=0.12;
  if(FAMOUS_EU.has(homeTeam)) bias+=0.08;
  const ch=Math.min(0.92,probs.home+bias);
  return {consensusHome:ch,edge:probs.home-ch};
}

// COLORS
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

function EVTable({scoreList,probs,homeName,awayName,myPick}) {
  const best=bestPick(scoreList,probs);
  const rows=[
    ...scoreList.slice(0,3).map(s=>({label:`Exacto ${s.score}`,ev:evForScore(s,probs),prob:s.p,pts:3})),
    {label:`Victoria ${homeName}`,ev:probs.home*1,prob:probs.home,pts:1},
    {label:"Empate",ev:probs.draw*1,prob:probs.draw,pts:1},
    {label:`Victoria ${awayName}`,ev:probs.away*1,prob:probs.away,pts:1},
  ].sort((a,b)=>b.ev-a.ev);

  return (
    <div style={{marginTop:14}}>
      <div style={{display:"flex",gap:8,marginBottom:10}}>
        <div style={{flex:1,background:`${C.accent}15`,border:`1px solid ${C.accent}44`,borderRadius:10,padding:"10px 14px"}}>
          <div style={{fontSize:10,color:C.accent,fontWeight:700,letterSpacing:1.5,marginBottom:3}}>PICK ÓPTIMO</div>
          <div style={{fontSize:15,fontWeight:800,color:C.text}}>{best.score}</div>
          <div style={{fontSize:11,color:C.muted}}>EV <span style={{color:C.gold,fontWeight:700}}>{best.ev.toFixed(3)}</span> · P {(best.prob*100).toFixed(1)}%</div>
        </div>
        <div style={{flex:1,background:`${C.orange}12`,border:`1px solid ${C.orange}44`,borderRadius:10,padding:"10px 14px"}}>
          <div style={{fontSize:10,color:C.orange,fontWeight:700,letterSpacing:1.5,marginBottom:3}}>TU PICK</div>
          <div style={{fontSize:15,fontWeight:800,color:C.text}}>{myPick||"—"}</div>
          <div style={{fontSize:11,color:C.muted}}>{myPick===best.score?"✓ Alineado con modelo":"⚠ Difiere del óptimo"}</div>
        </div>
      </div>
      <div style={{fontSize:10,color:C.muted,letterSpacing:1,marginBottom:6}}>COMPARACIÓN EV — λ=1.20, P(draw)×1.10</div>
      {rows.map((r,i)=>(
        <div key={i} style={{
          display:"flex",alignItems:"center",gap:8,
          background:i===0?`${C.accent}15`:C.surface,
          border:`1px solid ${i===0?C.accent+"44":C.border}`,
          borderRadius:8,padding:"7px 12px",marginBottom:5,
        }}>
          <div style={{flex:1,fontSize:12,color:i===0?C.accentLight:C.muted}}>{r.label}</div>
          <div style={{fontSize:11,color:C.muted,width:48,textAlign:"right"}}>{(r.prob*100).toFixed(1)}%</div>
          <div style={{fontSize:11,color:C.muted,width:24,textAlign:"right"}}>×{r.pts}</div>
          <div style={{fontSize:13,fontWeight:700,width:48,textAlign:"right",color:i===0?C.gold:C.muted}}>{r.ev.toFixed(3)}</div>
        </div>
      ))}
    </div>
  );
}

function MatchCard({match,expanded,onToggle}) {
  const rH=ELO[match.home]||1600;
  const rA=ELO[match.away]||1600;
  const probs=threeWay(rH,rA,match.host_boost);
  const {lA,lB}=xg(rH,rA,match.host_boost?100:60);
  const scoreList=scoreMatrix(lA,lB);
  const best=bestPick(scoreList,probs);
  const cons=consensusBias(match.home,probs);
  const played=match.result!==null&&match.result!==undefined&&!match.pending;
  const ptColor=match.pts===3?C.green:match.pts===1?C.gold:C.red;

  return (
    <div onClick={onToggle} style={{
      background:expanded?C.card:C.surface,
      border:`1px solid ${expanded?C.accent+"55":played?(match.pts===3?C.green+"33":match.pts===1?C.gold+"22":C.red+"22"):C.border}`,
      borderRadius:12,padding:"13px 16px",cursor:"pointer",transition:"all 0.2s",marginBottom:8,
    }}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:9}}>
        <div style={{display:"flex",gap:5,flexWrap:"wrap"}}>
          <span style={{fontSize:10,color:C.muted,background:C.border,padding:"2px 7px",borderRadius:8}}>G{match.group}</span>
          <span style={{fontSize:10,color:C.muted}}>{match.date}</span>
          {match.champion_pick&&<span style={{fontSize:10,color:C.gold,background:"rgba(240,192,64,0.15)",padding:"2px 7px",borderRadius:8}}>⭐ Campeona</span>}
        </div>
        {played?(
          <span style={{fontSize:11,padding:"2px 8px",borderRadius:10,fontWeight:700,background:`${ptColor}18`,color:ptColor,border:`1px solid ${ptColor}44`}}>
            {match.pts===3?"✓ Exacto":match.pts===1?"~ Resultado":"✗ Miss"} · {match.pts}pt
          </span>
        ):(
          <span style={{fontSize:11,padding:"2px 8px",borderRadius:10,fontWeight:700,background:`${C.orange}18`,color:C.orange,border:`1px solid ${C.orange}44`}}>
            Pick: {match.pick} {match.pick===best.score?"✓":""}
          </span>
        )}
      </div>

      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:11}}>
        <div>
          <div style={{fontSize:16,fontWeight:800,color:C.text}}>{match.home}</div>
          <div style={{fontSize:10,color:C.muted}}>Elo {rH}</div>
        </div>
        <div style={{textAlign:"center"}}>
          {played?(
            <>
              <div style={{fontSize:18,fontWeight:900,color:C.gold}}>{match.result}</div>
              <div style={{fontSize:10,color:C.muted}}>pick: {match.pick}</div>
            </>
          ):(
            <div style={{fontSize:11,color:C.muted,letterSpacing:2}}>VS</div>
          )}
        </div>
        <div style={{textAlign:"right"}}>
          <div style={{fontSize:16,fontWeight:800,color:C.text}}>{match.away}</div>
          <div style={{fontSize:10,color:C.muted}}>Elo {rA}</div>
        </div>
      </div>

      <ProbBar pHome={probs.home} pDraw={probs.draw} pAway={probs.away} homeTeam={match.home} awayTeam={match.away}/>

      {expanded&&(
        <div style={{marginTop:14,borderTop:`1px solid ${C.border}`,paddingTop:14}}>
          <div style={{display:"flex",gap:8,marginBottom:12}}>
            <div style={{flex:1,background:C.bg,borderRadius:8,padding:"9px 12px"}}>
              <div style={{fontSize:10,color:C.muted,marginBottom:2}}>xG</div>
              <div style={{fontSize:13,fontWeight:700}}>
                <span style={{color:C.accentLight}}>{lA.toFixed(2)}</span>
                <span style={{color:C.muted}}> — </span>
                <span style={{color:C.red}}>{lB.toFixed(2)}</span>
              </div>
            </div>
            <div style={{flex:1,background:C.bg,borderRadius:8,padding:"9px 12px"}}>
              <div style={{fontSize:10,color:C.muted,marginBottom:2}}>Δ Elo</div>
              <div style={{fontSize:13,fontWeight:700,color:C.gold}}>{rH-rA>0?"+":""}{rH-rA}</div>
            </div>
            <div style={{flex:1,background:C.bg,borderRadius:8,padding:"9px 12px"}}>
              <div style={{fontSize:10,color:C.muted,marginBottom:2}}>P(draw)*</div>
              <div style={{fontSize:13,fontWeight:700,color:C.orange}}>{(probs.draw*100).toFixed(0)}%</div>
            </div>
          </div>

          <div style={{marginBottom:12}}>
            <div style={{fontSize:10,color:C.muted,letterSpacing:1,marginBottom:7}}>MARCADORES MÁS PROBABLES</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:6}}>
              {scoreList.slice(0,6).map((s,i)=>(
                <div key={s.score} style={{
                  background:s.score===match.pick?`${C.orange}22`:i===0?`${C.accent}22`:C.bg,
                  border:`1px solid ${s.score===match.pick?C.orange:i===0?C.accent:C.border}`,
                  borderRadius:8,padding:"5px 11px",textAlign:"center",
                }}>
                  <div style={{fontSize:14,fontWeight:700,color:s.score===match.pick?C.orange:i===0?C.accentLight:C.text}}>{s.score}</div>
                  <div style={{fontSize:10,color:C.muted}}>{(s.p*100).toFixed(1)}%</div>
                  {s.score===match.pick&&<div style={{fontSize:8,color:C.orange}}>tu pick</div>}
                </div>
              ))}
            </div>
          </div>

          {match.pending&&<EVTable scoreList={scoreList} probs={probs} homeName={match.home} awayName={match.away} myPick={match.pick}/>}

          <div style={{marginTop:10,fontSize:11,color:C.muted,background:C.bg,borderRadius:8,padding:"7px 12px"}}>
            Consenso Avera: <span style={{color:C.text}}>{(cons.consensusHome*100).toFixed(0)}%</span> {match.home} ·
            Modelo: <span style={{color:C.accentLight}}>{(probs.home*100).toFixed(0)}%</span> ·
            Edge: <span style={{color:cons.edge<-0.05?C.green:C.muted}}>{(cons.edge*100).toFixed(0)}%</span>
          </div>
        </div>
      )}
    </div>
  );
}

function CalibrationPanel() {
  const r1Draws=R1.filter(m=>m.result&&m.result.split("-")[0]===m.result.split("-")[1]).length;
  const r1Goals=R1.reduce((s,m)=>{if(!m.result)return s;const[h,a]=m.result.split("-").map(Number);return s+h+a;},0);
  const r1Exact=R1.filter(m=>m.pts===3).length;
  const r1Result=R1.filter(m=>m.pts===1).length;
  const r1Miss=R1.filter(m=>m.pts===0).length;
  const r2Played=R2.filter(m=>m.result&&!m.pending);
  const r2Exact=r2Played.filter(m=>m.pts===3).length;

  return (
    <div style={{background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:18,marginBottom:16}}>
      <div style={{fontSize:11,color:C.accent,fontWeight:700,letterSpacing:1.5,marginBottom:12}}>
        RECALIBRACIÓN BAYESIANA POST-ROUND 1
      </div>
      <div style={{display:"flex",gap:8,marginBottom:14}}>
        {[
          {label:"P(empate) R1",value:`${(r1Draws/24*100).toFixed(0)}%`,sub:"prior: 22%",color:C.orange},
          {label:"λ obs. R1",value:(r1Goals/24/2).toFixed(2),sub:"prior: 1.35",color:C.accentLight},
          {label:"Exactos R1",value:r1Exact,sub:"de 24",color:C.green},
          {label:"Exactos R2",value:r2Exact,sub:`de ${r2Played.length}`,color:C.gold},
          {label:"Misses R1",value:r1Miss,sub:"0pt",color:C.red},
        ].map(s=>(
          <div key={s.label} style={{flex:1,background:C.bg,borderRadius:9,padding:"8px 4px",textAlign:"center"}}>
            <div style={{fontSize:16,fontWeight:900,color:s.color}}>{s.value}</div>
            <div style={{fontSize:8,color:C.muted,marginTop:1}}>{s.label}</div>
            <div style={{fontSize:8,color:C.muted,opacity:0.6}}>{s.sub}</div>
          </div>
        ))}
      </div>
      <div style={{fontSize:11,color:C.muted,lineHeight:1.7,background:C.bg,borderRadius:8,padding:"10px 12px"}}>
        <span style={{color:C.text,fontWeight:600}}>Posterior:</span> P(empate) obs. 37.5% vs prior 22%.
        Formato 48 equipos crea incentivo estructural al empate — tercer clasificado puede avanzar.
        λ recalibrado 1.35→1.20. Para R2 aplicamos boost ×1.10.<br/>
        <span style={{color:C.accent}}>Edge estratégico:</span> Apostar empate en partidos parejos tiene EV relativo positivo vs consenso narrativo.
      </div>
    </div>
  );
}

export default function App() {
  const [expanded,setExpanded]=useState(null);
  const [tab,setTab]=useState("pending");

  const r1Pts=R1.reduce((s,m)=>s+(m.pts||0),0);
  const r2Played=R2.filter(m=>m.result&&!m.pending);
  const r2Pts=r2Played.reduce((s,m)=>s+(m.pts||0),0);
  const totalPts=r1Pts+r2Pts;
  const totalExact=[...R1,...r2Played].filter(m=>m.pts===3).length;
  const pending=R2.filter(m=>m.pending||m.result===null);

  const dateGroups={};
  for(const m of pending){if(!dateGroups[m.date])dateGroups[m.date]=[];dateGroups[m.date].push(m);}
  const playedAll=[...R1,...r2Played];

  return (
    <div style={{minHeight:"100vh",background:C.bg,color:C.text,fontFamily:"'DM Sans','Segoe UI',sans-serif",padding:"22px 14px",maxWidth:660,margin:"0 auto"}}>
      <div style={{marginBottom:20}}>
        <div style={{fontSize:10,letterSpacing:3,color:C.accent,marginBottom:4,textTransform:"uppercase"}}>
          Quiniela Intelligence System · Avera 2026
        </div>
        <h1 style={{fontSize:24,fontWeight:900,margin:0,background:`linear-gradient(135deg,${C.text},${C.accentLight})`,WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>
          Mundial 2026
        </h1>
        <p style={{color:C.muted,fontSize:11,marginTop:4}}>
          Modelo recalibrado R1→R2 · λ=1.20 · P(draw)×1.10 · Sistema 3/1/6
        </p>
        <div style={{display:"flex",gap:7,marginTop:12}}>
          {[
            {label:"Pts",value:totalPts,color:C.gold},
            {label:"Posición",value:"#3",color:C.accentLight},
            {label:"Exactos",value:totalExact,color:C.green},
            {label:"Pendientes",value:pending.length,color:C.orange},
            {label:"Campeona",value:"🇫🇷",color:C.gold},
          ].map(s=>(
            <div key={s.label} style={{flex:1,background:C.surface,border:`1px solid ${C.border}`,borderRadius:9,padding:"7px 4px",textAlign:"center"}}>
              <div style={{fontSize:16,fontWeight:900,color:s.color}}>{s.value}</div>
              <div style={{fontSize:8,color:C.muted,marginTop:1}}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{display:"flex",gap:6,marginBottom:16}}>
        {[["pending",`Pendientes (${pending.length})`],["played",`Jugados (${playedAll.length})`],["calibration","Calibración"]].map(([key,label])=>(
          <button key={key} onClick={()=>setTab(key)} style={{
            padding:"7px 12px",borderRadius:18,border:"none",cursor:"pointer",
            fontSize:11,fontWeight:600,transition:"all 0.2s",
            background:tab===key?C.accent:C.surface,color:tab===key?"#fff":C.muted,
          }}>{label}</button>
        ))}
      </div>

      {tab==="calibration"&&<CalibrationPanel/>}

      {tab==="pending"&&Object.entries(dateGroups).map(([date,matches])=>(
        <div key={date}>
          <div style={{fontSize:10,color:C.accent,fontWeight:700,letterSpacing:2,marginBottom:8,marginTop:4}}>
            {date.toUpperCase()}
          </div>
          {matches.map((m,i)=>{
            const key=`${date}-${i}`;
            return <MatchCard key={key} match={m} expanded={expanded===key} onToggle={()=>setExpanded(expanded===key?null:key)}/>;
          })}
        </div>
      ))}

      {tab==="played"&&playedAll.map((m,i)=>(
        <MatchCard key={i} match={m} expanded={expanded===`p-${i}`} onToggle={()=>setExpanded(expanded===`p-${i}`?null:`p-${i}`)}/>
      ))}

      <div style={{marginTop:20,padding:"9px 13px",background:C.surface,borderRadius:8,border:`1px solid ${C.border}`,fontSize:10,color:C.muted,lineHeight:1.8}}>
        <span style={{color:C.accent,fontWeight:700}}>METODOLOGÍA · </span>
        Elo: eloratings.net. Poisson bivariado recalibrado post-R1. λ: 1.35→1.20. P(draw) ×1.10 formato 48 equipos.
        EV = P(exacto)×3 + P(resultado no exacto)×1. Sesgo consenso: LATAM +12%, EU famosas +8%.
      </div>
    </div>
  );
}
