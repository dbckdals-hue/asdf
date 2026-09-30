const {load,fmt,chart}=require('./h2.js');const f=process.argv[2];
const T0=Date.UTC(2026,8,28,10,0,0)/1000,STEP=300;const c=load(f,{});const run=c.run;
run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+T0);
const bar=(i,p)=>{const [d,t]=fmt(T0+i*STEP);return {high:p+.5,low:p-.5,sdate:d,stime:t}};
const hist=[];for(let i=0;i<140;i++)hist.push(bar(i,5000+(i%3)*.1));
const s=hist[60];c.registerPendingSignal('SP500','M0005','BEAR1',s.sdate,s.stime,4990,5,'REAL',0,s.sdate,s.stime,3,1);
const comp=hist.slice(0,61);let real=0,opened=null;
for(let k=61;k<140&&opened===null;k++){
  for(let p=1;p<=3;p++){const fb=bar(k,5000);const bs=[...comp,fb];run("lastTickEpoch="+(T0+k*STEP));run("requestQueue=[{seq:1,cycle:5,fileLabel:'M0005',itemName:'SP500',count:"+bs.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:5}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bs));}
  comp.push(hist[k]);real++;c.processLiveBar('M0005',5,hist[k].high,hist[k].low,hist[k].sdate,hist[k].stime,0);
  const sg=run('pendingSignals[0]');if(!sg){console.log(f,'resolved at',real);opened=real;break}
  if(sg.barsElapsedSinceRegistration>=26){console.log(f,'게이트 카운터 26 도달: 실제 완결봉',real);opened=real;}}
