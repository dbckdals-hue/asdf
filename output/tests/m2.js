const {load,fmt,chart}=require('./h2.js');
const T0=Date.UTC(2026,8,28,10,0,0)/1000;
function setup(f,tk,STEP){const c=load(f,{});const lab=tk?'T0100':'M0005',cyc=tk?100:5;c.run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+T0);
  const [d,t]=fmt(T0+60*STEP);if(tk)c.registerPendingSignal('SP500',lab,'BEAR1',d,t,4990,cyc,50,0,'REAL',0,d,t);else c.registerPendingSignal('SP500',lab,'BEAR1',d,t,4990,cyc,'REAL',0,d,t,3,1);
  return {c,lab,cyc};}
function bars(n,STEP,start){const b=[];for(let i=0;i<n;i++){const [d,t]=fmt(T0+(start+i)*STEP);b.push({high:5000.5,low:4999.5,sdate:d,stime:t,filled:false});}return b}
function warm(c,tk,bs,cyc,lab){c.run("lastTickEpoch="+(T0+(60+bs.length)*(tk?60:300)));c.run("requestQueue=[{seq:1,cycle:"+cyc+",fileLabel:'"+lab+"',itemName:'SP500',count:"+bs.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cyc+"}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bs));}
const ctr=c=>c.run('pendingSignals[0]?pendingSignals[0].barsElapsedSinceRegistration:"resolved"');
for(const [nm,tk,STEP] of [['tick',true,60],['min',false,300]]){
 for(const f of [nm+'.js',nm+'_b.js']){
  const out=[];
  // 상황1: 실시간이 적게 셈(카운터 13) - 차트엔 신호 후 완결봉 20개 + 형성봉 1개 (게이트 26 미만: 판정 안 남)
  {const {c,lab,cyc}=setup(f,tk,STEP);c.run("pendingSignals[0].barsElapsedSinceRegistration=13");warm(c,tk,bars(60+20+1,STEP,0),cyc,lab);out.push('상황1 실시간13 → 워밍업 후 '+ctr(c)+' (차트 완결 20봉+형성 1봉)');}
  // 상황2: 카운터가 부풀어 있음(40) - 차트엔 완결 20봉
  {const {c,lab,cyc}=setup(f,tk,STEP);c.run("pendingSignals[0].barsElapsedSinceRegistration=40");warm(c,tk,bars(60+20+1,STEP,0),cyc,lab);out.push('상황2 카운터40(부풀림) → '+ctr(c));}
  // 상황3: 재조회 구간이 신호 시각을 못 덮음(창 시작이 신호 이후) - 카운터를 건드리면 안 됨
  {const {c,lab,cyc}=setup(f,tk,STEP);c.run("pendingSignals[0].barsElapsedSinceRegistration=13");warm(c,tk,bars(15,STEP,70),cyc,lab);out.push('상황3 구간이 신호를 못 덮음(13) → '+ctr(c));}
  console.log(f.padEnd(11),out.join(' | '));}}
