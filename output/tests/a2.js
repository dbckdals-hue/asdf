const {load,fmt,chart,lines}=require('./h2.js');const D=Date.UTC(2026,8,29,12,0,0)/1000;
const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+(D+60)+";totalTicksReceived=0");const [sd,st]=fmt(D+60);
c.registerPendingSignal('SP500','T0100','BEAR1',sd,st,4990,100,50,0,'REAL',0,sd,st);c.run("pendingSignals[0].barsElapsedSinceRegistration=2");
const b=[];for(let s=0;s<=1800;s+=60){const [d,t]=fmt(D+s);b.push({high:5000.5,low:4999.5,sdate:d,stime:t,filled:false});}
c.run("lastTickEpoch="+(D+1800)+";requestQueue=[{seq:1,cycle:100,fileLabel:'T0100',itemName:'SP500',count:"+b.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:100}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(b));
const sig=lines(c).filter(l=>l.split(',')[2]==='GATE_COUNT_SYNC').length;const diag=c.run('diagnosticBuffer.filter(function(x){return x.indexOf("GATE_COUNT_SYNC_INIT")>=0}).length');
console.log('첫 동기화(큰 차이) → 신호파일 알림',sig,'건 / 진단로그 INIT',diag,'건', sig===0&&diag===1?'PASS':'FAIL');
