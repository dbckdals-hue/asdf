const {load,fmt,chart,rw}=require('./h2.js');
const T0=Date.UTC(2026,8,28,10,0,0)/1000;
function bench(f){const tk=/tick/.test(f);const store={};const c=load(f,store);let logs=0,logch=0;c.Main.MessageLog=(m)=>{logs++;logch+=String(m).length;};
 const cyc=tk?100:5,lab=tk?'T0100':'M0005',step=tk?60:300;
 c.run("lastTickEpoch="+T0+";scriptStartTime=Date.now()-1e6;");
 const N=300;
 for(let i=0;i<N;i++){const [d,t]=fmt(T0+i*7);const px=5000+(i%9)*0.25;const kind=['BULL1','BEAR1','BULL2','BEAR2'][i%4];
  try{ if(tk)c.registerPendingSignal('SP500',lab,kind,d,t,px+(kind[1]=='U'?40:-40),cyc,50,0,'REAL',0,d,t);
  else c.registerPendingSignal('SP500',lab,kind,d,t,px+(kind[1]=='U'?40:-40),cyc,'REAL',0,d,t,3,0.5+i);}catch(e){console.log('reg err',e.message);break}}
 const np=c.run('pendingSignals.length');
 // ticks
 let x=1;const r=()=>{x=(x*1664525+1013904223)%4294967296;return x/4294967296};
 const s0=c.__st.saves,e0=c.__st.sets;const t0=process.hrtime.bigint();
 const base=T0+3000;
 for(let i=0;i<3000;i++){const [d,t]=fmt(base+i*2);c.updatePendingSignals(5000+Math.round((r()-0.5)*10)/4,d,t);}
 const tickMs=Number(process.hrtime.bigint()-t0)/1e6/3000;
 // warm responses
 const all=rw(5000,7,T0,step);let wms=0;const s1=c.__st.saves,e1=c.__st.sets,l1=logs;
 const R=15;
 for(let k=0;k<R;k++){const n=4000+k*60;c.run("lastTickEpoch="+(T0+n*step));
  c.run("requestQueue=[{seq:1,cycle:"+cyc+",fileLabel:'"+lab+"',itemName:'SP500',count:"+n+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cyc+"}];baseTargetList=targetList;");
  const a=process.hrtime.bigint();try{c.Main_OnRcvChartEx(chart(all.slice(0,n)));}catch(e){console.log('warm err',e.message)}wms+=Number(process.hrtime.bigint()-a)/1e6;}
 try{c.flushExcelDirtyShards&&c.flushExcelDirtyShards(true)}catch(e){}
 return {f,pending:np,alive:c.run('pendingSignals.length'),tickMsPerTick:tickMs.toFixed(3),warmMsPerResp:(wms/R).toFixed(1),
  tickPhase_saves:s1-s0,tickPhase_sets:e1-e0,warmPhase_saves:c.__st.saves-s1,warmPhase_sets:c.__st.sets-e1,logLines:logs,logChars:logch,excelKB:Math.round(Object.values(store).join('').length/1024)};}
const out=process.argv.slice(2).map(f=>{try{return bench(f)}catch(e){return {f,err:e.message}}});
console.table(out);
