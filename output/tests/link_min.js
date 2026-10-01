const {load,fmt}=require('./h2.js');
const D=Date.UTC(2026,9,1,12,0,0)/1000; // 12:00:00 UTC = 5분 버킷 경계
function mkChart(bars){const n=bars.length;const g=i=>bars[n-1-i];return {GetHigh:(k,i)=>i<n?g(i).high:null,GetLow:(k,i)=>i<n?g(i).low:null,GetSDate:(k,i)=>Number(g(i).sdate),GetSTime:(k,i)=>{const [h,m,s]=g(i).stime.split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>5};}
const px=i=>(i===50?5010:(i===60?4990:5000+((i*7919)%23)*0.25));
const c=load('min.js',{});c.run("scriptStartTime=Date.now()-1e6");
c.run("var __b=[];var __pl=processLiveBar;processLiveBar=function(fl,p,h,l,sd,st,g){if(fl==='M0005')__b.push({h:h,l:l,st:st});return __pl.apply(this,arguments)}");
function tick(i){const [d,t]=fmt(D+i);c.run("marketDataObj={current:"+px(i)+",date:"+d+",time:"+t.replace(/:/g,'')+"0000};lastTickEpoch="+(D+i)+";");c.Main_OnUpdateMarket('ESZ26',20001,0);}
// 1초 1틱. 버킷0 = 0~299초. 응답은 120초 시점(버킷0의 40% 지남)에 도착. 버킷0 초반(0~119초)에 극값(고가) 존재.
const resp=120;for(let i=0;i<resp;i++)tick(i);
const bars=[];for(let j=0;j<10;j++){const [d,t]=fmt(D-(10-j)*300+1);bars.push({high:5001,low:4999,sdate:d,stime:t,filled:false});}
c.run("requestQueue=[{seq:1,cycle:5,fileLabel:'M0005',itemName:'SP500',count:10,sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:5}];baseTargetList=targetList;");
c.Main_OnRcvChartEx(mkChart(bars));c.run("__b=[]");
for(let i=resp;i<700;i++)tick(i);
let H=-1e9,L=1e9;for(let i=0;i<300;i++){H=Math.max(H,px(i));L=Math.min(L,px(i));}
let H2=-1e9,L2=1e9;for(let i=resp;i<300;i++){H2=Math.max(H2,px(i));L2=Math.min(L2,px(i));}
const b=c.run("__b.slice()");console.log("DEBUG bars",b.length,"ticks",c.run("totalTicksReceived"),"lb keys",c.run("Object.keys(liveBuilders).length"),"M0005 bucket",c.run("liveBuilders.M0005.bucket"));
console.log('분봉: 응답 시점=버킷의 120초째. 차트 기준 첫 봉(0~299초) 고/저='+H+'/'+L+' | 실시간이 완성해 계산기에 넣은 첫 봉 고/저='+b[0].h+'/'+b[0].l+' (응답 후 틱만으로 계산한 값='+H2+'/'+L2+')');
console.log('둘째 봉부터는 차트와 같은가: 실시간 둘째 봉 고/저='+b[1].h+'/'+b[1].l+' 차트 기준(300~599초)='+Math.max(...[...Array(300)].map((_,k)=>px(300+k)))+'/'+Math.min(...[...Array(300)].map((_,k)=>px(300+k))));
