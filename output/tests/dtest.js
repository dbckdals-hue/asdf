const {load,fmt,chart,lines}=require('./h2.js');
const D=Date.UTC(2026,8,29,12,0,0)/1000;
function feed(c,startSec,secs,tpm,price){ // 실시간 틱 공급: 분당 tpm 틱
  const n=Math.round(secs/60*tpm);for(let i=0;i<n;i++){const s=startSec+Math.floor(i/tpm*60);const [d,t]=fmt(D+s);
    c.run("marketDataObj={current:"+(price+(i%3)*0.25)+",date:"+d+",time:"+t.replace(/:/g,'')+"00};");c.Main_OnUpdateMarket('ESZ26',20001,0);}}
function chartBars(cycle,startSec,endSec,tpm){const b=[];const dt=cycle/tpm*60;for(let s=startSec;s<=endSec;s+=dt){const [d,t]=fmt(D+Math.floor(s));b.push({high:5000.5,low:4999.5,sdate:d,stime:t,filled:false});}return b}
function warm(c,cyc,bars){c.run("requestQueue=[{seq:1,cycle:"+cyc+",fileLabel:'T"+String(cyc).padStart(4,'0')+"',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cyc+"}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bars));}
const syncLines=c=>lines(c).filter(l=>l.split(',')[2]==='GATE_COUNT_SYNC');
function scenario(name,{cycle,chartTpm,feedTpm,passEvery,minutes}){
  const c=load('tick.js',{});const lab='T'+String(cycle).padStart(4,'0');c.run("scriptStartTime=Date.now()-1e6");
  feed(c,0,60,feedTpm,5000); // 시작 틱(lastTickEpoch 설정)
  const [sd,st]=fmt(D+60);c.run("lastTickEpoch="+(D+60));
  c.registerPendingSignal('SP500',lab,'BEAR1',sd,st,4990,cycle,50,0,'REAL',0,sd,st);
  let t=60;const end=60+minutes*60;
  while(t<end){const seg=Math.min(passEvery?passEvery*60:end-t,end-t);feed(c,t,seg,feedTpm,5000);t+=seg;
    if(passEvery&&t<end){c.run("lastTickEpoch="+(D+t));warm(c,cycle,chartBars(cycle,0,t,chartTpm));}}
  c.run("lastTickEpoch="+(D+end));warm(c,cycle,chartBars(cycle,0,end,chartTpm));
  const L=syncLines(c);const diag=c.__w.filter(w=>/diagnostic/.test(w[0])).length; // 진단파일은 하트비트 때 flush
  console.log('['+name+']',L.length?L[L.length-1].split(',').slice(5).join(' , ').slice(0,330):'(기록 없음)');
  return L;}
scenario('D1 수신틱이 차트의 절반',{cycle:100,chartTpm:100,feedTpm:50,passEvery:0,minutes:20});
scenario('D2 봉이 느려 재조회에 계속 잘림',{cycle:785,chartTpm:100,feedTpm:100,passEvery:4,minutes:26});
scenario('D0 정상(수신=차트) 기록 없어야',{cycle:100,chartTpm:100,feedTpm:100,passEvery:0,minutes:20});
// D3 부풀림
{const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");const lab='T0100';feed(c,0,60,100,5000);c.run("lastTickEpoch="+(D+60));const [sd,st]=fmt(D+60);
 c.registerPendingSignal('SP500',lab,'BEAR1',sd,st,4990,100,50,0,'REAL',0,sd,st);c.run("pendingSignals[0].barsElapsedSinceRegistration=40");
 c.run("lastTickEpoch="+(D+1500));warm(c,100,chartBars(100,0,1500,100));const L=syncLines(c);console.log('[D3 카운터 40으로 부풀림]',L.length?L[0].split(',').slice(5).join(' , ').slice(0,300):'(없음)');}
scenario('D4 재조회 주기 ≥ 봉 소요시간의 2배(분당100틱,785틱봉,6분 주기)',{cycle:785,chartTpm:100,feedTpm:100,passEvery:16,minutes:48});
scenario('D5 빠른 봉 + 3분 주기 재조회',{cycle:785,chartTpm:400,feedTpm:400,passEvery:3,minutes:30});
