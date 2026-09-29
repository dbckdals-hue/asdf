// regression: behaviour that must stay identical before/after patches
const {load,fmt,chart,rw,lines}=require('./h2.js');
const T0=Date.UTC(2026,8,28,10,0,0)/1000;
function isTick(f){return /tick/.test(f)}
function sumLines(c){ // canonical, time-independent view
  const set=new Set();
  lines(c).forEach(l=>{const p=l.split(',');const k=p[2];
    if(['BULL1','BULL2','BEAR1','BEAR2'].includes(k))set.add(['SIG',p[1],k,p[3],p[4],p[5]].join('|'));
    else if(k==='STATS_IMMEDIATE')set.add(['STATSI',p[1],p[8],p[3],p[4],p[5],p[6]].join('|'));
    else if(k==='STATUS_ACHIEVED'||k==='STATUS_INVALID'){const m=/\((\d+H\d+M)\)/.exec(p[6]);const rs=(p[7]||'').split(' / ')[0].replace(/\(.*$/,'');set.add(['ST',p[1],k,p[8],p[3],p[4],p[5],m&&m[1],rs].join('|'));}
    else if(k==='PRETTY2_CONFIRMED')set.add(['P2',p[1],p[6],p[3],p[4],p[5],p[7],p[8]].join('|'));});
  return [...set].sort();}
function pend(c){return JSON.parse(c.run('JSON.stringify(pendingSignals.map(function(s){return {pk:pkOf(s),state:s.state,n:s.barsElapsedSinceRegistration,la:s.lastAppliedBarEpoch,pb:s.pullbackPrice||null}}))')).sort((a,b)=>a.pk<b.pk?-1:1)}
function warm(c,f,bars,cycle){const tk=isTick(f);const lab=(tk?'T':'M')+String(cycle).padStart(4,'0');
  c.run("requestQueue=[{seq:1,cycle:"+cycle+",fileLabel:'"+lab+"',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cycle+"}];baseTargetList=targetList;");
  c.Main_OnRcvChartEx(chart(bars));}
exports.run=function(f){
  const tk=isTick(f);const res={};
  // ---- S1: realtime judgement + persistence roundtrip
  {const store={};const c=load(f,store);const cyc=tk?100:5,lab=tk?'T0100':'M0005';const STEP=tk?600:300;
   c.run("lastTickEpoch="+T0+";scriptStartTime=Date.now()-1e6;");
   const specs=[['BULL1',5000],['BEAR1',5001],['BULL2',4999.5],['BEAR2',5000.5],['BULL1',5003],['BEAR1',4997]];
   specs.forEach((s,i)=>{const [d,t]=fmt(T0+i);
     if(tk)c.registerPendingSignal('SP500',lab,s[0],d,t,s[1],cyc,50,0,'REAL',0,d,t);
     else c.registerPendingSignal('SP500',lab,s[0],d,t,s[1],cyc,'REAL',0,d,t,3,0.5+i);});
   for(let k=1;k<=30;k++){const [d,t]=fmt(T0+k*STEP);const b=5000+((k*7)%5-2)*0.25;
     if(tk)c.processLiveBar(cyc,b+0.5,b-0.5,d,t);else c.processLiveBar(lab,cyc,b+0.5,b-0.5,d,t,0);
     if(k===10){c.savePendingState();res.S3_before=pend(c);
        const c2=load(f,JSON.parse(JSON.stringify(store)));c2.loadPendingStateFromExcel();res.S3_after=pend(c2);}}
   let x=12345;const r=()=>{x=(x*1664525+1013904223)%4294967296;return x/4294967296};
   const base=T0+31*STEP;
   for(let i=0;i<4000;i++){const [d,t]=fmt(base+i*20);c.updatePendingSignals(5000+Math.round((r()-0.5)*12)/4,d,t);}
   res.S1_lines=sumLines(c);res.S1_pending=pend(c);}
  // ---- S2: WARM path, several seeds, 3 passes with data growth
  res.S2=[];
  for(let seed=1;seed<=60;seed++){const c=load(f,{});const cyc=tk?100:5;const step=tk?60:300;
    const all=rw(900,seed,T0,step);c.run("scriptStartTime=Date.now()-1e6;");
    [600,700,800,900].forEach(n=>{c.run("lastTickEpoch="+(T0+n*step));warm(c,f,all.slice(0,n),cyc);});
    res.S2.push({seed,lines:sumLines(c),pending:pend(c)});}
  return res;};
if(require.main===module){const f=process.argv[2];console.log(JSON.stringify(exports.run(f)));}
