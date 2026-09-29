const {load,fmt,chart,rw,lines}=require('./h2.js');
const T0=Date.UTC(2026,8,28,10,0,0)/1000;
const snap=c=>c.run('JSON.stringify(pendingSignals.map(function(s){return {pk:pkOf(s),state:s.state,n:s.barsElapsedSinceRegistration,la:s.lastAppliedBarEpoch,lj:s.lastJudgedBarEpoch,pb:s.pullbackPrice||null,pw:s.pullbackWhen||null}}).sort(function(a,b){return a.pk<b.pk?-1:1}))');
function warm(c,tk,bars,cyc){const lab=(tk?'T':'M')+String(cyc).padStart(4,'0');
 c.run("requestQueue=[{seq:1,cycle:"+cyc+",fileLabel:'"+lab+"',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cyc+"}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bars));}
for(const nm of ['tick','min']){const tk=nm==='tick';const res={};
 for(const which of ['orig/','']){const f=which+nm+'.js';let rtOk=0,tot=0,badSeeds=[];let saves=0,sets=0;
  for(let seed=1;seed<=40;seed++){const store={};const c=load(f,store);const lab=tk?'T0100':'M0005',cyc=tk?100:5,STEP=tk?600:300;c.run("lastTickEpoch="+T0+";scriptStartTime=Date.now()-1e6");
   let x=seed*104729;const rn=()=>{x=(x*1664525+1013904223)%4294967296;return x/4294967296};
   for(let i=0;i<30;i++){const [d,t]=fmt(T0+i);const kind=['BULL1','BEAR1','BULL2','BEAR2'][i%4];const pr=5000+Math.round((rn()-0.5)*20)/4;
     if(tk)c.registerPendingSignal('SP500',lab,kind,d,t,pr,cyc,50,0,'REAL',0,d,t);else c.registerPendingSignal('SP500',lab,kind,d,t,pr,cyc,'REAL',0,d,t,3,i+1);}
   c.savePendingState();
   let clk=T0+40;for(let k=1;k<=20;k++){for(let j=0;j<30;j++){const [d,t]=fmt(clk+=7);c.updatePendingSignals(5000+Math.round((rn()-0.5)*20)/4,d,t);}
     const [d,t]=fmt(T0+k*STEP);const b=5000;if(tk)c.processLiveBar(cyc,b+.5,b-.5,d,t);else c.processLiveBar(lab,cyc,b+.5,b-.5,d,t,0);}
   // warm passes with same data (bars end before now)
   const bars=rw(300,seed,T0-300*(tk?60:300),tk?60:300);for(let i=0;i<3;i++){c.run("lastTickEpoch="+T0);warm(c,tk,bars,cyc);}
   saves+=c.__st.saves;sets+=c.__st.sets;
   c.savePendingState();const before=snap(c);const c2=load(f,JSON.parse(JSON.stringify(store)));c2.loadPendingStateFromExcel();const after=snap(c2);
   tot++;if(before===after)rtOk++;else badSeeds.push(seed);}
  res[which?'orig':'new']={roundtripOK:rtOk+'/'+tot,badSeeds:badSeeds.slice(0,5),excelSaves:saves,excelSetData:sets};}
 console.log(nm,JSON.stringify(res));}
