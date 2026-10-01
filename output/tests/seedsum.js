const {load,fmt,lines}=require('./h2.js');const D=Date.UTC(2026,9,1,12,0,0)/1000;
let rs=11;const rnd=()=>{rs=(rs*1664525+1013904223)%4294967296;return rs/4294967296};
const P=[],Q=[];let a=4200,b=4300;for(let i=0;i<600;i++){a+=(Math.floor(rnd()*9)-4)*0.1;b+=(Math.floor(rnd()*9)-4)*0.1;P.push(Math.round(a*10)/10);Q.push(Math.round(b*10)/10)}
function bars(S,upTo,per){const o=[];for(let s=0;s+per<=upTo;s+=per){let h=-1e18,l=1e18;for(let i=s;i<s+per;i++){h=Math.max(h,S[i]);l=Math.min(l,S[i])}const [d,t]=fmt(D+s);o.push({high:h,low:l,sdate:d,stime:t,filled:false})}
 const s=Math.floor(upTo/per)*per;if(s<upTo){let h=-1e18,l=1e18;for(let i=s;i<upTo;i++){h=Math.max(h,S[i]);l=Math.min(l,S[i])}const [d,t]=fmt(D+s);o.push({high:h,low:l,sdate:d,stime:t,filled:false})}return o}
function chart(bs){const n=bs.length;const g=i=>bs[n-1-i];return {GetHigh:(k,i)=>i<n?g(i).high:null,GetLow:(k,i)=>i<n?g(i).low:null,GetSDate:(k,i)=>Number(g(i).sdate),GetSTime:(k,i)=>{const [h,m,s]=g(i).stime.split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>null}}
const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");
c.run("baseTargetList=[30,35,40].map(function(x){return {code:'ESZ26',nameEn:'SP500',cycle:x}});targetList=baseTargetList;currentIndex=0;");
for(let i=0;i<400;i++){const [d,t]=fmt(D+i);c.run("marketDataObj={current:"+P[i]+",date:"+d+",time:"+t.replace(/:/g,'')+"0000};lastTickEpoch="+(D+i)+";");c.Main_OnUpdateMarket('ESZ26',20001,0)}
let g=0;while(c.run("totalPassesCompleted")<1&&g++<50){c.run("lastRemoveObjectAt=0;pendingRemoveObjects=[]");c.processNext();
  if(c.run("waitingForResponse")){const cy=c.run("currentCycle");const S=(cy===35)?Q:P;c.Main_OnRcvChartEx(chart(bars(S,400,cy)));}}
const L=lines(c).filter(l=>l.split(',')[2]==='LIVE_SEED_SUMMARY');console.log(L.join('\n'));
require('fs').writeFileSync('seedsum_line.txt',L[0]||'');
