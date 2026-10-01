const {load,fmt}=require('./h2.js');
const D=Date.UTC(2026,9,1,12,0,0)/1000;
let rs=99;const rnd=()=>{rs=(rs*1664525+1013904223)%4294967296;return rs/4294967296};
const NT=7000;const P=[];let px=4200;for(let i=0;i<NT;i++){px+=(Math.floor(rnd()*9)-4)*0.1;P.push(Math.round(px*10)/10)}
function chart(bars){const n=bars.length;const g=i=>bars[n-1-i];return {GetHigh:(k,i)=>i<n?g(i).high:null,GetLow:(k,i)=>i<n?g(i).low:null,GetSDate:(k,i)=>Number(g(i).sdate),GetSTime:(k,i)=>{const [h,m,s]=g(i).stime.split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>0}}
function run(file){
 const isTick=/tick/.test(file);global.gc&&global.gc();const m0=process.memoryUsage().heapUsed;
 const c=load(file,{});c.run("scriptStartTime=Date.now()-1e6");
 function tick(i){const [d,t]=fmt(D+i);c.run("marketDataObj={current:"+P[i]+",date:"+d+",time:"+t.replace(/:/g,'')+"0000};lastTickEpoch="+(D+i)+";");}
 // 1) 틱당 처리시간 (Main_OnUpdateMarket, 빌더 195/110개 + 신호 0개)
 const t0=process.hrtime.bigint();
 for(let i=0;i<5000;i++){tick(i);c.Main_OnUpdateMarket('ESZ26',20001,0)}
 const perTickUs=Number(process.hrtime.bigint()-t0)/1e3/5000;
 global.gc&&global.gc();const m1=process.memoryUsage().heapUsed;
 // 2) 전체 프레임 한 바퀴 워밍업(응답 처리 시간 + 이어받기 성공 수)
 const cycles=isTick?[...Array(195)].map((_,k)=>30+5*k):[...Array(110)].map((_,k)=>k+1);
 let wms=0,seeded=0,fail=0;
 for(const cyc of cycles){
   const per=isTick?cyc:cyc*60; // 틱봉: 틱수, 분봉: 초
   let bars=[];
   if(isTick){const origin=Math.floor(rnd()*cyc);for(let s=origin;s+cyc<=5000;s+=cyc){let h=-1e18,l=1e18;for(let i=s;i<s+cyc;i++){h=Math.max(h,P[i]);l=Math.min(l,P[i])}const [d,t]=fmt(D+s);bars.push({high:h,low:l,sdate:d,stime:t,filled:false});}
     // 형성 중 봉
     const last=bars.length?Math.floor((5000-origin)/cyc)*cyc+origin:0;let h=-1e18,l=1e18;for(let i=last;i<5000;i++){h=Math.max(h,P[i]);l=Math.min(l,P[i])}if(last<5000){const [d,t]=fmt(D+last);bars.push({high:h,low:l,sdate:d,stime:t,filled:false})}}
   else{const b0=Math.floor(D/per);for(let b=b0;b*per<D+5000;b++){let h=-1e18,l=1e18,any=false;for(let i=Math.max(0,b*per-D);i<Math.min(5000,(b+1)*per-D);i++){h=Math.max(h,P[i]);l=Math.min(l,P[i]);any=true}if(!any)continue;const [d,t]=fmt(b*per+1);bars.push({high:h,low:l,sdate:d,stime:t,filled:false})}}
   const lab=(isTick?'T':'M')+String(cyc).padStart(4,'0');
   c.run("lastTickEpoch="+(D+4999)+";requestQueue=[{seq:1,cycle:"+cyc+",fileLabel:'"+lab+"',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cyc+"}];baseTargetList=targetList;");
   const a=process.hrtime.bigint();c.Main_OnRcvChartEx(chart(bars));wms+=Number(process.hrtime.bigint()-a)/1e6;
 }
 try{seeded=cycles.reduce((n,cy)=>n+(c.run("(getLiveReseedStats("+cy+").seeded||0)")),0);fail=cycles.reduce((n,cy)=>n+(c.run("(getLiveReseedStats("+cy+").seedFail||0)")),0)}catch(e){}
 global.gc&&global.gc();const m2=process.memoryUsage().heapUsed;
 return {file,perTickUs:perTickUs.toFixed(1),warmCycleMs:wms.toFixed(0),seeded,fail,heapKB_afterTicks:Math.round((m1-m0)/1024),heapKB_afterWarm:Math.round((m2-m0)/1024)};
}
const res=process.argv.slice(2).map(run);console.table(res);
