const {load,fmt}=require('./h2.js');
const D=Date.UTC(2026,9,1,12,0,0)/1000;const out=[];const ok=(n,c,e)=>out.push((c?'PASS ':'FAIL ')+n+(e?'  '+e:''));
const px=i=>(i===50?5010:(i===60?4990:5000+((i*7919)%23)*0.25));
function chart(bars){const n=bars.length;const g=i=>bars[n-1-i];return {GetHigh:(k,i)=>i<n?g(i).high:null,GetLow:(k,i)=>i<n?g(i).low:null,GetSDate:(k,i)=>Number(g(i).sdate),GetSTime:(k,i)=>{const [h,m,s]=g(i).stime.split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>5}}
for(const f of ['min_pre523.js','min.js']){
 const c=load(f,{});c.run("scriptStartTime=Date.now()-1e6;var __lb=[];var __pl=processLiveBar;processLiveBar=function(fl,p,h,l,sd,st,g){if(fl==='M0005')__lb.push({h:h,l:l,sd:sd,st:st});return __pl.apply(this,arguments)}");
 function tick(i){const [d,t]=fmt(D+i);c.run("marketDataObj={current:"+px(i)+",date:"+d+",time:"+t.replace(/:/g,'')+"0000};lastTickEpoch="+(D+i)+";");c.Main_OnUpdateMarket('ESZ26',20001,0)}
 // 스크립트는 100초에 켜졌고(버킷0=0~299초) 120초에 워밍업 응답. 차트의 형성 중 봉은 0초부터의 고저(스파이크 포함)
 for(let i=100;i<120;i++)tick(i);
 const bars=[];for(let j=12;j>=1;j--){const [d,t]=fmt(D-j*300+1);bars.push({high:5001,low:4999,sdate:d,stime:t,filled:false})}
 let H=-1e9,L=1e9;for(let i=0;i<120;i++){H=Math.max(H,px(i));L=Math.min(L,px(i))}
 const [d0,t0]=fmt(D+1);bars.push({high:H,low:L,sdate:d0,stime:t0,filled:false}); // 형성 중 봉(시각 = 버킷시작+1초)
 c.run("requestQueue=[{seq:1,cycle:5,fileLabel:'M0005',itemName:'SP500',count:13,sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:5}];baseTargetList=targetList;");
 c.Main_OnRcvChartEx(chart(bars));
 const bcAfterWarm=c.run("liveCalcs.M0005.barCount");c.run("__lb=[]");
 for(let i=120;i<700;i++)tick(i);
 const lb=c.run("__lb.slice()");let H2=-1e9,L2=1e9;for(let i=0;i<300;i++){H2=Math.max(H2,px(i));L2=Math.min(L2,px(i))}
 ok(f+' 첫 실시간 봉 고/저가 = 차트 기준('+H2+'/'+L2+')',lb.length>0&&lb[0].h===H2&&lb[0].l===L2,'실제='+(lb[0]?lb[0].h+'/'+lb[0].l:'-'));
 ok(f+' 실시간 봉 시각 = 버킷시작+1초('+fmt(D+1)[1]+')',lb.length>0&&lb[0].st===fmt(D+1)[1],'실제='+(lb[0]?lb[0].st:'-'));
 const bcNow=c.run("liveCalcs.M0005.barCount");
 ok(f+' 계산기 봉 수 = 차트 완결봉 12 + 실시간 완성봉 '+lb.length+' = '+(12+lb.length)+' (중복 없음)',bcNow===12+lb.length,'실제 '+bcNow+' (응답 직후 '+bcAfterWarm+')');
}
console.log(out.join('\n'));
