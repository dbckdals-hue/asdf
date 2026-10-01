// 가짜 엔진: 실시간 틱 스트림과 차트 틱봉을 같은 틱에서 만들되, 차트의 봉 경계 시작 위치(origin)를 모른 채 어긋나게 만든다.
const vm=require('vm'),fs=require('fs');
function run({dropRate=0,origin=17,N=50,seconds=900,tps=3}){
  let now=1e12,t={},logs=[];const ctx0={};
  const code=fs.readFileSync('1an_gold_tick_probe.txt','utf8').replace(/var COLLECT_SEC = \d+;/,'var COLLECT_SEC = '+seconds+';').replace(/var CHART_COUNT = \d+;/,'var CHART_COUNT = 600;');
  const D=Date.UTC(2026,9,1,12,0,0)/1000;
  // 원본 틱 스트림(차트가 보는 것): 과거 10000틱 + 수집 구간
  const total=10000+seconds*tps;const all=[];let px=4200;
  for(let i=0;i<total;i++){px+=((i*7919)%7-3)*0.1;const sec=D-10000/tps+Math.floor(i/tps);const d=new Date(sec*1000);all.push({p:Math.round(px*10)/10,sec});}
  const fmtT=s=>{const d=new Date(s*1000);return [d.toISOString().slice(0,10).replace(/-/g,''),d.toISOString().slice(11,19)]};
  // 차트 봉: origin 만큼 어긋난 위치부터 N틱씩
  const chartBars=[];for(let j=origin;j+N<=all.length;j+=N){let h=-1e18,l=1e18;for(let q=j;q<j+N;q++){h=Math.max(h,all[q].p);l=Math.min(l,all[q].p)}chartBars.push({h,l,sec:all[j+N-1].sec});}
  chartBars.push({h:4200,l:4200,sec:all[all.length-1].sec}); // 형성중 봉(idx0)
  const ch={GetHigh:(k,i)=>{const b=chartBars[chartBars.length-1-i];return b?b.h:null},GetLow:(k,i)=>{const b=chartBars[chartBars.length-1-i];return b?b.l:null},
    GetSDate:(k,i)=>Number(fmtT(chartBars[chartBars.length-1-i].sec)[0]),GetSTime:(k,i)=>{const [h,m,s]=fmtT(chartBars[chartBars.length-1-i].sec)[1].split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>N};
  const ctx={Date:class extends Date{constructor(...a){a.length?super(...a):super(now)}static now(){return now}},Math,Number,Array,isFinite,console,CHART_PERIOD_TICK:1,CHART_REQCOUNT_BAR:1,ReqChartItem:function(){},IndicatorInfo:function(){},
    Main:{MessageLog:m=>logs.push(m),ReqMarketData(){},SetTimer:(i,m)=>t[i]=now+m,KillTimer:i=>delete t[i],RemoveObject(){},ReqChartEx(){setTimeout(()=>{},0);ctx.__pending=true;return true}}};
  vm.createContext(ctx);vm.runInContext(code.replace('var CYCLE = 50;','var CYCLE = '+N+';'),ctx);ctx.Main_OnStart();
  // 실시간 틱 공급: 수집구간 틱만, dropRate 만큼 누락
  let rnd=12345;const rr=()=>{rnd=(rnd*1664525+1013904223)%4294967296;return rnd/4294967296};
  for(let i=10000;i<total;i++){if(rr()<dropRate)continue;const [d,tm]=fmtT(all[i].sec);ctx.Main_OnRcvMarketData({current:all[i].p,date:d,time:tm.replace(/:/g,'')+'0000'});ctx.Main_OnUpdateMarket('GCZ26',20001,0);}
  now+=seconds*1000;ctx.Main_OnTimer(1);ctx.Main_OnRcvChartEx(ch);
  return logs.filter(l=>/offset|판정|수신틱 \d+개 \//.test(l));
}
for(const [name,o] of [['정상(실시간=차트, 경계어긋남 17)',{origin:17}],['정상(어긋남 0)',{origin:0}],['실시간 틱 3% 누락',{origin:17,dropRate:0.03}],['실시간 틱 20% 누락',{origin:17,dropRate:0.2}]]){
  console.log('['+name+']');console.log(run(o).map(l=>'  '+l.replace(/^\[[^\]]*\] /,'')).join('\n'));}
