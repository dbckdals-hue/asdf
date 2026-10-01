// 1초 타이머 방식 시뮬레이션: 가상시계로 150초 진행, 틱 공급, 응답
const vm=require('vm'),fs=require('fs');
let now=1e12,t={},logs=[],files=[],pend=false;
const D=Date.UTC(2026,9,1,12,0,0)/1000;const fmtT=s=>{const d=new Date(s*1000);return [d.toISOString().slice(0,10).replace(/-/g,''),d.toISOString().slice(11,19)]};
const N=30,all=[];let px=4200;for(let i=0;i<5000;i++){px+=((i*7919)%7-3)*0.1;all.push({p:Math.round(px*10)/10,sec:D+Math.floor(i/3)})}
const bars=[];for(let j=11;j+N<=all.length;j+=N){let h=-1e18,l=1e18;for(let q=j;q<j+N;q++){h=Math.max(h,all[q].p);l=Math.min(l,all[q].p)}bars.push({h,l,sec:all[j+N-1].sec})}bars.push({h:1,l:1,sec:all[all.length-1].sec});
const ch={GetHigh:(k,i)=>{const b=bars[bars.length-1-i];return b?b.h:null},GetLow:(k,i)=>{const b=bars[bars.length-1-i];return b?b.l:null},GetSDate:(k,i)=>Number(fmtT(bars[bars.length-1-i].sec)[0]),GetSTime:(k,i)=>{const [h,m,s]=fmtT(bars[bars.length-1-i].sec)[1].split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>N};
const ctx={Date:class extends Date{constructor(...a){a.length?super(...a):super(now)}static now(){return now}},Math,Number,Array,isFinite,CHART_PERIOD_TICK:1,CHART_REQCOUNT_BAR:1,ReqChartItem:function(){},IndicatorInfo:function(){},
 Main:{MessageLog:m=>logs.push(m),PrintOnFile:(p,c)=>files.push(c),ReqMarketData(){return 1},SetTimer:(i,m)=>t[i]=now+m,KillTimer:i=>delete t[i],RemoveObject(){},ReqChartEx(){pend=true;return true}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('1an_gold_tick_probe.txt','utf8'),ctx);ctx.Main_OnStart();
let ti=0;for(let step=0;step<400;step++){const nx=Math.min(...Object.values(t));if(!isFinite(nx))break;
  while(ti<450&&all[ti].sec-D<= (nx-1e12)/1000+0){const [d,tm]=fmtT(all[ti].sec);ctx.Main_OnRcvMarketData({current:all[ti].p,date:d,time:tm.replace(/:/g,'')+'0000'});ctx.Main_OnUpdateMarket('GCZ26',20001,0);ti++}
  now=nx;const id=Object.keys(t).find(k=>t[k]===nx);delete t[id];ctx.Main_OnTimer(+id);
  if(pend){pend=false;ctx.Main_OnRcvChartEx(ch);}}
console.log(logs.map(l=>l.replace(/^\[[^\]]*\] /,'')).join('\n'));console.log('파일 저장 횟수',files.length);
