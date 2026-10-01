const {load,fmt}=require('./h2.js');
const D=Date.UTC(2026,9,1,12,0,0)/1000;const out=[];const ok=(n,c,e)=>out.push((c?'PASS ':'FAIL ')+n+(e?'  '+e:''));
let rs=4242;const rnd=()=>{rs=(rs*1664525+1013904223)%4294967296;return rs/4294967296};
const P=[];let px=4200;for(let i=0;i<4000;i++){px+=(Math.floor(rnd()*9)-4)*0.1;P.push(Math.round(px*10)/10)}
function mkBars(file,upTo,per,origin){const b=[];for(let s=origin;s<upTo;s+=per){const e=Math.min(s+per-1,upTo-1);let h=-1e18,l=1e18;for(let i=s;i<=e;i++){h=Math.max(h,P[i]);l=Math.min(l,P[i])}const [d,t]=fmt(D+s);b.push({high:h,low:l,sdate:d,stime:t,filled:false})}return b}
function chart(bars){const n=bars.length;const g=i=>bars[n-1-i];return {GetHigh:(k,i)=>i<n?g(i).high:null,GetLow:(k,i)=>i<n?g(i).low:null,GetSDate:(k,i)=>Number(g(i).sdate),GetSTime:(k,i)=>{const [h,m,s]=g(i).stime.split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>50}}
function setup(file){const c=load(file,{});c.run("scriptStartTime=Date.now()-1e6;var __lb=[];var __pl=processLiveBar;processLiveBar=function(p,h,l,sd,st){if(p===50)__lb.push({h:h,l:l,sd:sd,st:st,tk:totalTicksReceived});return __pl.apply(this,arguments)}");return c}
function tick(c,i){const [d,t]=fmt(D+i);c.run("marketDataObj={current:"+P[i]+",date:"+d+",time:"+t.replace(/:/g,'')+"0000};");c.Main_OnUpdateMarket('ESZ26',20001,0)}
function warm(c,bars){c.run("lastTickEpoch="+(D+9999)+";requestQueue=[{seq:1,cycle:50,fileLabel:'T0050',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:50}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bars))}
function hl(a,b){let h=-1e18,l=1e18;for(let i=a;i<=b;i++){h=Math.max(h,P[i]);l=Math.min(l,P[i])}return [h,l]}
for(const f of ['tick_pre523.js','tick.js']){
 // A) 형성 중 봉에 17틱 쌓인 시점에 응답
 let c=setup(f);for(let i=0;i<1017;i++)tick(c,i);warm(c,mkBars(f,1017,50,0));c.run("__lb=[]");for(let i=1017;i<1260;i++)tick(c,i);
 let L=c.run("__lb.slice()");const exp=[1050,1100,1150,1200,1250];
 const [h1,l1]=hl(1000,1049);
 ok(f+' A) 응답 후 실시간 봉 완성 시점이 차트 경계(틱번호 '+exp.join('/')+')와 같다',JSON.stringify(L.map(x=>x.tk))===JSON.stringify(exp),'실제='+L.map(x=>x.tk).join('/'));
 ok(f+' A) 첫 실시간 봉 고/저가가 차트 기준(1000~1049틱 '+h1+'/'+l1+')과 같다',L.length>0&&L[0].h===h1&&L[0].l===l1,'실제='+(L[0]?L[0].h+'/'+L[0].l:'-'));
 ok(f+' A) 실시간 봉 시각이 차트 기준(첫 틱 '+fmt(D+1000)[1]+')',L.length>0&&L[0].st===fmt(D+1000)[1],'실제='+(L[0]?L[0].st:'-'));
 if(f==='tick.js'){ok(f+' A) 이어받기 성공 기록',c.run("getLiveReseedStats(50).seeded")===1)}
 // B) 응답 처리 시점에 로그가 차트 스냅샷보다 15틱 더 진행(경계 통과) -> 재생봉 1개
 c=setup(f);for(let i=0;i<1060;i++)tick(c,i);c.run("__lb=[]");warm(c,mkBars(f,1045,50,0));const lbB=c.run("__lb.slice()");c.run("__lb=[]");for(let i=1060;i<1260;i++)tick(c,i);
 L=c.run("__lb.slice()");
 if(f==='tick.js'){ok(f+' B) 스냅샷 이후 완성된 봉을 재생해서 처리(1050 경계)',lbB.length===1&&lbB[0].tk===1060&&lbB[0].h===hl(1000,1049)[0],'재생봉='+lbB.length);
  ok(f+' B) 이후 경계도 차트와 같다(1100/1150/1200/1250)',JSON.stringify(L.map(x=>x.tk))===JSON.stringify([1100,1150,1200,1250]),'실제='+L.map(x=>x.tk).join('/'))}
 else ok(f+' B) (예전 방식은 재생 개념 없음 - 경계가 어긋남)',true,'실제 경계='+L.map(x=>x.tk).slice(0,3).join('/'));
 // C) 스크립트를 막 켠 직후(틱 로그 10개) -> 실패하고 예전처럼 빈 빌더
 c=setup(f);for(let i=1007;i<1017;i++)tick(c,i);warm(c,mkBars(f,1017,50,0));
 if(f==='tick.js')ok(f+' C) 로그 부족이면 이어받기 실패(예전 방식으로 동작)',c.run("getLiveReseedStats(50).seedFail")===1&&c.run("liveBuilders[50].count")===0);
 // D) 실시간 틱이 차트와 다르면(틱 누락) 못 찾고 예전 방식
 c=setup(f);let r2=9;for(let i=0;i<1017;i++){r2=(r2*1103515245+12345)%2147483648;if(r2%100<4)continue;tick(c,i)}warm(c,mkBars(f,1017,50,0));
 if(f==='tick.js')ok(f+' D) 틱 4% 누락 시 못 찾음 -> 안전하게 예전 방식',c.run("getLiveReseedStats(50).seedFail")===1);
}
console.log(out.join('\n'));
