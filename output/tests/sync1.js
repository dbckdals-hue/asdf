const {load,fmt,chart,lines}=require('./h2.js');
// ── 테스트 1: 실시간 구독이 워밍업(차트)에 맞춰지는가 ──────────────────────────
// 틱 스트림 20,000개. 차트 봉 = 연속 N틱 묶음(진짜). 워밍업 시점 i_w에 차트 응답(완결봉 + 형성중 봉)을 받고, 그 뒤 실시간이 만드는 봉을 차트 봉과 비교.
const N=100;let x=7,p=5000;const r=()=>{x=(x*1664525+1013904223)%4294967296;return x/4294967296};
const ticks=[];for(let i=0;i<20000;i++){p+=Math.round((r()-0.5)*6)/4;ticks.push(p);}
const D=Date.UTC(2026,8,29,12,0,0)/1000;const tm=i=>fmt(D+i); // 1틱/초
function chartTruth(upto){const b=[];for(let k=0;k*N<upto;k++){const s=ticks.slice(k*N,Math.min((k+1)*N,upto));const [d,t]=tm(Math.min((k+1)*N,upto)-1);b.push({high:Math.max(...s),low:Math.min(...s),sdate:d,stime:t,filled:false,complete:(k+1)*N<=upto});}return b}
function run1(iw){
  const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");
  let liveBars=[];c.run("var __lb=[];processLiveBar=function(p,h,l,sd,st){if(p===100)__lb.push({h:h,l:l,st:st});};marketDataObj={};");
  // 실시간 틱 공급 (워밍업 이전 구간은 무시: 워밍업이 리셋)
  function feed(a,b){for(let i=a;i<b;i++){const [d,t]=tm(i);c.run("marketDataObj={current:"+ticks[i]+",date:"+d+",time:"+t.replace(/:/g,'')+"00};");c.Main_OnUpdateMarket('ESZ26',20001,0);}}
  feed(0,iw);
  // 워밍업 응답 처리(빌더 재시작 발생)
  const bars=chartTruth(iw);c.run("lastTickEpoch="+(D+iw)+";requestQueue=[{seq:1,cycle:"+N+",fileLabel:'T0100',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+N+"}];baseTargetList=targetList;");
  c.run("__lb.length=0");c.Main_OnRcvChartEx(chart(bars));
  feed(iw,iw+1000);
  const live=JSON.parse(c.run("JSON.stringify(__lb)"));
  const truth=chartTruth(iw+1000).filter(b=>b.complete);
  let same=0;live.forEach(l=>{if(truth.some(t=>Math.abs(t.high-l.h)<1e-9&&Math.abs(t.low-l.l)<1e-9))same++;});
  return {iw,off:iw%N,live:live.length,same};}
console.log('틱 100개=1봉. 워밍업 시점마다 워밍업 이후 실시간이 만든 봉 중 차트 봉과 같은 것');
for(const iw of [3000,3020,3050,3077,3099,3100])console.log(' 워밍업 시점 틱#'+iw,'(형성중 봉에 이미 '+(iw%N)+'틱)','→ 실시간 봉',run1(iw).live,'개 중 차트와 일치',run1(iw).same,'개');
