const {load,fmt}=require('./h2.js');
const D=Date.UTC(2026,9,1,12,0,0)/1000;
function mkChart(bars,ind){const n=bars.length;const g=i=>bars[n-1-i];
 return {GetHigh:(k,i)=>i<n?g(i).high:null,GetLow:(k,i)=>i<n?g(i).low:null,GetSDate:(k,i)=>Number(g(i).sdate),GetSTime:(k,i)=>{const [h,m,s]=g(i).stime.split(':').map(Number);return (h*10000+m*100+s)*10000},
  GetIndicatorData:ind};}
function tick(c,i,pr){const [d,t]=fmt(D+i);c.run("marketDataObj={current:"+pr+",date:"+d+",time:"+t.replace(/:/g,'')+"00};");c.run("lastTickEpoch="+(D+i));c.Main_OnUpdateMarket('ESZ26',20001,0);}
function warm(c,reqCyc,bars,ind){c.run("requestQueue=[{seq:1,cycle:"+reqCyc+",fileLabel:'T"+String(reqCyc).padStart(4,'0')+"',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+reqCyc+"}];baseTargetList=targetList;");c.Main_OnRcvChartEx(mkChart(bars,ind));}
const px=i=>5000+((i*7919)%23)*0.25;
function chartBars(ticksN,per){const b=[];for(let j=0;j*per+per<=ticksN+per;j++){const s=j*per,e=Math.min(s+per-1,ticksN-1);if(s>=ticksN)break;let h=-1e9,l=1e9;for(let i=s;i<=e;i++){h=Math.max(h,px(i));l=Math.min(l,px(i));}const [d,t]=fmt(D+e);b.push({high:h,low:l,sdate:d,stime:t,filled:false});}return b;}
const out=[];
// 1) #주기=50, 요청 100 -> 실시간이 50틱으로 인식하는가
{const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");const tk=1000+17;for(let i=0;i<tk;i++)tick(c,i,px(i));
 warm(c,100,chartBars(tk,50),()=>50);
 out.push('1) 요청100/#주기=50 -> 실시간 빌더 50틱 존재: '+c.run("!!liveBuilders[50]&&liveBuilders[50].n===50")+', 100틱 빌더는 이번 응답으로 안 바뀜(n=100 유지): '+c.run("liveBuilders[100]?liveBuilders[100].n:'없음'")+', 재시도큐에 100 들어감: '+c.run("retryQueue.some(function(t){return t.cycle===100})"));}
// 2) #주기 null -> 어떻게 되나
{const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");const tk=1000+17;for(let i=0;i<tk;i++)tick(c,i,px(i));
 warm(c,100,chartBars(tk,50),()=>null);
 out.push('2) #주기=null -> 50틱 데이터가 100틱 빌더로 저장됨: '+c.run("liveBuilders[100].n===100")+' (n='+c.run("liveBuilders[100].n")+'), 재시도큐에 들어감: '+c.run("retryQueue.length>0"));}
{const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");const tk=1000+17;for(let i=0;i<tk;i++)tick(c,i,px(i));
 warm(c,100,chartBars(tk,50),()=>7);
 out.push('2b) #주기=7(5단위 아님) -> 100틱 빌더로 저장: '+c.run("liveBuilders[100].n===100")+', 재시도큐: '+c.run("retryQueue.length>0"));}
// 3) 봉 경계 정렬: 워밍업 응답 시점에 형성중 봉에 17틱이 쌓여 있을 때
{const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");c.run("var __b=[];var __pl=processLiveBar;processLiveBar=function(p,h,l,sd,st){if(p===50)__b.push(totalTicksReceived);return __pl.apply(this,arguments)}");
 const tk=1000+17;for(let i=0;i<tk;i++)tick(c,i,px(i));
 warm(c,50,chartBars(tk,50),()=>50);c.run("__b=[]");
 for(let i=tk;i<tk+200;i++)tick(c,i,px(i));
 const live=c.run("__b.slice()");
 out.push('3) 틱봉: 응답 시점 형성중 봉 17틱. 차트의 다음 봉 경계(틱번호)=1050,1100,1150,1200 / 실시간이 완성한 봉 경계='+live.join(',')+' -> 어긋남 '+(live[0]-1050)+'틱');}
console.log(out.join('\n'));
