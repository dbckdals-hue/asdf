const {load,fmt,chart,lines}=require('./h2.js');
const file=process.argv[2]||'orig/tick.js';
const D=Date.UTC(2026,8,29,0,0,0)/1000; const at=(h,m,s)=>D+h*3600+m*60+(s||0);
// chart truth: 58s bars. price stays BELOW target 7718.50 from 12:52 on (so state truly WAITING), touches at 13:11-13:12, then jumps to 7740 later
function mkbars(){const b=[];for(let t=at(12,20,0);t<=at(20,30,19);t+=58){const m=(t-D)/60;let hi,lo;
  if(m<12*60+46){hi=7724;lo=7721;} else if(m<12*60+52){hi=7723;lo=7719.5;}
  else if(m<13*60+30){hi=7718.3;lo=7716;} else {hi=7740.75;lo=7735;}
  const [d,s]=fmt(t);b.push({high:hi,low:lo,sdate:d,stime:s});}return b;}
function scenario(realtimeTickBeforeWarm){
  const c=load(file,{});const run=c.run;run("scriptStartTime=Date.now()-1e6");
  const [sd,st]=fmt(at(12,46,12));run("lastTickEpoch="+at(12,46,12));
  c.registerPendingSignal('SP500','T0785','BEAR2',sd,st,7718.5,785,50,0,'REAL',0,sd,st);
  const tick=(t,p)=>{const [d,s]=fmt(t);c.updatePendingSignals(p,d,s)};
  tick(at(12,46,12),7722.75);tick(at(12,52,21),7718.25);            // 눌림 -> 대기중 (모달과 동일)
  for(let k=1;k<=13;k++){const [d,s]=fmt(at(12,46,12)+k*115);c.processLiveBar(785,7718,7716,d,s);} // 실시간 카운터 13
  if(realtimeTickBeforeWarm)tick(at(20,30,19),7740.75);            // 실시간 틱 1개 (WARM 직전)
  const bars=mkbars();run("lastTickEpoch="+at(20,30,19));
  run("requestQueue=[{seq:1,cycle:785,fileLabel:'T0785',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:785}];baseTargetList=targetList;");
  c.Main_OnRcvChartEx(chart(bars));
  const st_=lines(c).filter(l=>/STATUS_/.test(l)).map(l=>l.split(',')[2]+' '+(l.split(',')[7]||'').split(' / ')[0]);
  const hist=lines(c).filter(l=>/STATUS_/.test(l)).map(l=>(l.split(' / HISTORY:')[1]||'').split(' -> ').map(x=>x.replace(/@.*$/,'').replace('PULLBACK_CONFIRMED','눌림확인').replace('WAITING','대기중')));
  return {result:st_,history:hist[0]};}
console.log('A) 실시간 틱 없이 WARM만  :',JSON.stringify(scenario(false)));
console.log('B) WARM 직전 실시간 틱(20:30:19, 7740.75) 1개:',JSON.stringify(scenario(true)));
// 달성 후 감시목록/재추적 여부 확인
{const c=load(file,{});const run=c.run;run("scriptStartTime=Date.now()-1e6");const [sd,st]=fmt(at(12,46,12));run("lastTickEpoch="+at(12,46,12));
 c.registerPendingSignal('SP500','T0785','BEAR2',sd,st,7718.5,785,50,0,'REAL',0,sd,st);
 const tick=(t,p)=>{const [d,s]=fmt(t);c.updatePendingSignals(p,d,s)};tick(at(12,46,12),7722.75);tick(at(12,52,21),7718.25);
 for(let k=1;k<=13;k++){const [d,s]=fmt(at(12,46,12)+k*115);c.processLiveBar(785,7718,7716,d,s);} tick(at(20,30,19),7740.75);
 const bars=mkbars();
 for(let p=1;p<=3;p++){run("lastTickEpoch="+at(20,30,19));run("requestQueue=[{seq:1,cycle:785,fileLabel:'T0785',itemName:'SP500',count:"+bars.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:785}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bars));
  console.log('C) WARM 통과 #'+p+' 후 감시목록 개수:',run('pendingSignals.length'),'| 신호줄 재등록:',lines(c).filter(l=>/,BEAR2,/.test(l)).length);}}
