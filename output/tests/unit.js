const {load,fmt,chart,rw,lines}=require('./h2.js');
const T0=Date.UTC(2026,8,28,10,0,0)/1000;const out=[];
const ok=(name,cond,extra)=>{out.push((cond?'PASS ':'FAIL ')+name+(extra?'  '+extra:''));};
function warm(c,tk,bars,cyc){const lab=(tk?'T':'M')+String(cyc).padStart(4,'0');
 c.run("requestQueue=[{seq:1,cycle:"+cyc+",fileLabel:'"+lab+"',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cyc+"}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bars));}
const res={};
for(const which of ['orig/','']){for(const nm of ['tick','min']){const f=which+nm+'.js',tk=nm==='tick',tag=(which?'orig':'new')+'-'+nm;const r={};
 // U4 PRETTY2 replays
 {const c=load(f,{});const cyc=tk?100:5,step=tk?60:300;const bars=rw(600,1,T0,step);c.run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+(T0+600*step));
  for(let i=0;i<5;i++)warm(c,tk,bars,cyc);
  r.p2=lines(c).filter(l=>l.split(',')[2]==='PRETTY2_CONFIRMED').length;
  // changed content must be rewritten
  if(!which){c.__w.length=0;c.writePretty2Events('SP500','T0100',[{sdate:'20260928',stime:'10:00:00',price:5000,kind:'BULL1',confirmed:false,cases:[]}]);
   c.writePretty2Events('SP500','T0100',[{sdate:'20260928',stime:'10:00:00',price:5000,kind:'BULL1',confirmed:false,cases:[]}]);
   c.writePretty2Events('SP500','T0100',[{sdate:'20260928',stime:'10:00:00',price:5000,kind:'BULL1',confirmed:true,cases:[1,2]}]);
   r.p2change=lines(c).length;}}
 // U5 flapping: history size + differential final outcome
 {const c=load(f,{});const lab=tk?'T0100':'M0005',cyc=tk?100:5,STEP=tk?600:300;c.run("lastTickEpoch="+T0);
  const [d,t]=fmt(T0);if(tk)c.registerPendingSignal('SP500',lab,'BEAR1',d,t,5000,cyc,50,0,'REAL',0,d,t);else c.registerPendingSignal('SP500',lab,'BEAR1',d,t,5000,cyc,'REAL',0,d,t,3,1);
  for(let i=0;i<1000;i++){const [dd,tt]=fmt(T0+1+i);c.updatePendingSignals(i%2?4999:5001,dd,tt);}
  const s=c.run('pendingSignals[0]');r.hist=s.stateHistory.length;r.hjson=JSON.stringify(s).length;r.state=s.state;}
 // U5b differential: random flapping in closed gate then gate opens then resolution
 {let results=[];for(let seed=1;seed<=40;seed++){const c=load(f,{});const lab=tk?'T0100':'M0005',cyc=tk?100:5,STEP=tk?600:300;c.run("lastTickEpoch="+T0);
   let x=seed*7919;const rn=()=>{x=(x*1664525+1013904223)%4294967296;return x/4294967296};
   const specs=[['BULL1',5000],['BEAR1',5000],['BULL2',5000.5],['BEAR2',4999.5]];
   specs.forEach((sp,i)=>{const [d,t]=fmt(T0+i);if(tk)c.registerPendingSignal('SP500',lab,sp[0],d,t,sp[1],cyc,50,0,'REAL',0,d,t);else c.registerPendingSignal('SP500',lab,sp[0],d,t,sp[1],cyc,'REAL',0,d,t,3,1+i);});
   let clk=T0+10;for(let k=1;k<=40;k++){for(let j=0;j<20;j++){const [d,t]=fmt(clk+=5);c.updatePendingSignals(5000+Math.round((rn()-0.5)*8)/4,d,t);}
     const [d,t]=fmt(T0+k*STEP);const b=5000;if(tk)c.processLiveBar(cyc,b+.5,b-.5,d,t);else c.processLiveBar(lab,cyc,b+.5,b-.5,d,t,0);}
   for(let j=0;j<300;j++){const [d,t]=fmt(T0+50*STEP+j*30);c.updatePendingSignals(5000+Math.round((rn()-0.5)*16)/4,d,t);}
   results.push(lines(c).filter(l=>/STATUS_/.test(l)).map(l=>{const p=l.split(',');return [p[2],p[3],p[4],p[5],p[8],(p[7]||'').split(' / ')[0]].join('|')}).sort().join(';')+'#'+c.run('pendingSignals.map(function(s){return s.kind+s.state+s.barsElapsedSinceRegistration})').join(','));}
  r.diff=results;}
 // U6 dirty shards & saves
 {const store={};const c=load(f,store);const lab=tk?'T0100':'M0005',cyc=tk?100:5;c.run("lastTickEpoch="+T0);
  for(let i=0;i<60;i++){const [d,t]=fmt(T0+i);const p=lab;if(tk)c.registerPendingSignal('SP500',p,i%2?'BULL1':'BEAR1',d,t,5000+i,cyc,50,0,'REAL',0,d,t);else c.registerPendingSignal('SP500',p,i%2?'BULL1':'BEAR1',d,t,5000+i,cyc,'REAL',0,d,t,3,i+1);}
  c.savePendingState();c.run('excelDirtyShards={}');
  for(let i=0;i<500;i++){const [d,t]=fmt(T0+100+i);c.updatePendingSignals(4000,d,t);} // price far below: no state change for BEAR? BEAR: price<target => with gate closed no change; BULL: price<target => PULLBACK change
  r.dirtyAfterTicks=c.run('Object.keys(excelDirtyShards).length');
  // pure no-change ticks (price exactly at target)
  c.run('excelDirtyShards={}');
  for(let i=0;i<500;i++){const [d,t]=fmt(T0+700+i);c.updatePendingSignals(4000,d,t);}
  r.dirtyNoChange=c.run('Object.keys(excelDirtyShards).length');
  // warm repeated with same data -> number of Excel saves
  const c2=load(f,{});c2.run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+(T0+700*(tk?60:300)));const bars=rw(700,3,T0,tk?60:300);
  for(let i=0;i<4;i++)warm(c2,tk,bars,cyc);
  r.saves=c2.__st.saves;r.setCalls=c2.__st.sets;
  // shard overflow warning
  const msgs=[];const c3=load(f,{});c3.Main.MessageLog=m=>msgs.push(m);c3.run("lastTickEpoch="+T0);
  const [d,t]=fmt(T0);if(tk)c3.registerPendingSignal('SP500',lab,'BEAR1',d,t,5000,cyc,50,0,'REAL',0,d,t);else c3.registerPendingSignal('SP500',lab,'BEAR1',d,t,5000,cyc,'REAL',0,d,t,3,1);
  const sg=c3.run('pendingSignals[0]');for(let i=0;i<600;i++)sg.stateHistory.push({t:'x',s:'PULLBACK_CONFIRMED(09/28 10:00:00)@5000.00',epoch:null});
  c3.excelMarkDirty(sg);c3.flushExcelDirtyShards();r.warn=msgs.some(m=>/셀 한계/.test(m));}
 // U7 bar cache
 if(tk){const store={};const c=load(f,store);const bars=rw(700,1,T0,60);c.run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+(T0+700*60));warm(c,true,bars,100);
  r.Ecells=Object.keys(store).filter(k=>/^E\d/.test(k)).length;r.hasCacheVar=c.run("typeof barHistoryCache")!=='undefined';}
 res[tag]=r;}}
console.log(JSON.stringify(res,null,1).replace(/"diff": \[[^\]]*\]/g,m=>'"diff": [..'+(m.split('",').length)+' cases]'));
const eqd=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
for(const nm of ['tick','min']){ok('U5b '+nm+' 게이트닫힘 왕복 후 최종 판정 결과(40 시나리오) 수정 전후 동일',eqd(res['orig-'+nm].diff,res['new-'+nm].diff));}
console.log(out.join('\n'));
