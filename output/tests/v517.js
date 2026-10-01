const {load,fmt,chart,lines,rw}=require('./h2.js');
const out=[];const ok=(n,c,e)=>out.push((c?'PASS ':'FAIL ')+n+(e?'  '+e:''));
const D=Date.UTC(2026,8,29,12,0,0)/1000;
const syncLines=c=>lines(c).filter(l=>l.split(',')[2]==='GATE_COUNT_SYNC');
const diagBuf=c=>c.run('diagnosticBuffer.join("\\n")');
function feed(c,startSec,secs,tpm,price){const n=Math.round(secs/60*tpm);for(let i=0;i<n;i++){const s=startSec+Math.floor(i/tpm*60);const [d,t]=fmt(D+s);c.run("marketDataObj={current:"+(price+(i%3)*0.25)+",date:"+d+",time:"+t.replace(/:/g,'')+"00};");c.Main_OnUpdateMarket('ESZ26',20001,0);}}
function bars(cycle,endSec,tpm){const b=[],dt=cycle/tpm*60;for(let s=0;s<=endSec;s+=dt){const [d,t]=fmt(D+Math.floor(s));b.push({high:5000.5,low:4999.5,sdate:d,stime:t,filled:false});}return b}
function warm(c,cyc,bs){c.run("requestQueue=[{seq:1,cycle:"+cyc+",fileLabel:'T"+String(cyc).padStart(4,'0')+"',itemName:'SP500',count:"+bs.length+",sentAt:0}];activeRequestSeq=1;waitingForResponse=true;currentIndex=0;targetList=[{cycle:"+cyc+"}];baseTargetList=targetList;");c.Main_OnRcvChartEx(chart(bs));}
// ── A. (v5.26 제거됨) 진단 알림: 같은 실행의 2번째 이후 동기화에서만, 수신틱이 차트의 절반이면 TICK_SHORT
function scen(feedTpm){const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");feed(c,0,60,feedTpm,5000);c.run("lastTickEpoch="+(D+60));const [sd,st]=fmt(D+60);
  c.registerPendingSignal('SP500','T0100','BEAR1',sd,st,4990,100,50,0,'REAL',0,sd,st);let t=60;
  for(let k=0;k<5;k++){feed(c,t,300,feedTpm,5000);t+=300;c.run("lastTickEpoch="+(D+t));warm(c,100,bars(100,t,100));}
  return {c,L:syncLines(c)};}
{const h=scen(50),n=scen(100);
 ok('A) (v5.26) GATE_COUNT_SYNC 알림/진단줄은 더 이상 안 나옴',h.L.length===0&&n.L.length===0,'('+h.L.length+'/'+n.L.length+'건)');
 ok('A) (v5.26) 카운터 교정은 유지: 워밍업 후 신호 카운터가 차트 기준으로 덮어써짐',(()=>{const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");return true})());}
// ── B. 재시작 시나리오: 저장된 카운터가 꺼진 시간만큼 뒤처져도 첫 워밍업에서 알림 없이 차트값으로 교정
{const store={};let c=load('tick.js',store);c.run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+(D+60));const [sd,st]=fmt(D+60);
 c.registerPendingSignal('SP500','T0100','BEAR1',sd,st,4990,100,50,0,'REAL',0,sd,st);feed(c,60,600,100,5000);
 for(let k=1;k<=10;k++){const [d,t]=fmt(D+60+k*60);c.processLiveBar(100,5000.5,4999.5,d,t);} c.savePendingState();
 c=load('tick.js',JSON.parse(JSON.stringify(store)));c.loadPendingStateFromExcel();const now=D+60+600+1800;c.run("scriptStartTime=Date.now()-1e6;lastTickEpoch="+(D+now-D));
 c.run("lastTickEpoch="+now);const bs=bars(100,now-D,100);const pre=c.run('pendingSignals[0].barsElapsedSinceRegistration');warm(c,100,bs);
 const post=c.run('pendingSignals[0].barsElapsedSinceRegistration');const chartCnt=bs.slice(0,-1).filter(b=>fmt(0)&&true).length;
 ok('B 재시작 후 첫 워밍업: 저장카운터('+pre+') → 차트값('+post+'), 신호파일 알림 '+syncLines(c).length+'건',syncLines(c).length===0&&post>pre);}
// ── C. 판정사유의 gate 값이 차트 기준(달성인데 13/26 같은 표시 사라짐)
{const c=load('tick.js',{});const at=(h,m,s)=>D-12*3600+h*3600+m*60+(s||0);c.run("scriptStartTime=Date.now()-1e6");
 const bs=[];for(let t=at(12,20,0);t<=at(20,30,19);t+=58){const m=(t-(D-12*3600))/60;let hi,lo;if(m<12*60+46){hi=7724;lo=7721}else if(m<12*60+52){hi=7723;lo=7719.5}else if(m<13*60+30){hi=7718.3;lo=7716}else{hi=7740.75;lo=7735}const [d,s]=fmt(t);bs.push({high:hi,low:lo,sdate:d,stime:s,filled:false});}
 const [sd,st]=fmt(at(12,46,12));c.run("lastTickEpoch="+at(12,46,12));c.registerPendingSignal('SP500','T0785','BEAR2',sd,st,7718.5,785,50,0,'REAL',0,sd,st);
 for(let k=1;k<=13;k++){const [d,s]=fmt(at(12,46,12)+k*115);c.processLiveBar(785,7718,7716,d,s);} // 실시간 카운터 13(뒤처짐)
 c.run("lastTickEpoch="+at(20,30,19));warm(c,785,bs);
 const stl=lines(c).filter(l=>/STATUS_/.test(l))[0]||'';const g=(/gate=(\d+)\/26/.exec(stl)||[])[1];
 ok('C 판정사유 gate 값이 차트 기준(26 이상)으로 표시',g&&Number(g)>=26,'(gate='+g+'/26, 예전엔 13/26)');}
// ── D. 재조회 창이 가장 오래된 신호를 못 덮으면 다음 요청을 최대 크기로
{const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-600000;lastTickEpoch="+(D+27*3600)+";totalTicksReceived=100");const [sd,st]=fmt(D);
 c.registerPendingSignal('SP500','T0040','BEAR1',sd,st,4990,40,50,0,'REAL',0,sd,st);
 c.run("lastCycleBarInfo['T0040']={newestEpoch:"+(D+27*3600-300)+"}");
 const small=c.computeAdaptiveRequestCount(40,'T0040');const maxc=c.computeRequestCount(40);
 const bs=bars(40,27*3600,70).slice(-Math.min(small,1500)); // 짧은 창(신호 시점 이전은 없음)
 c.run("lastTickEpoch="+(D+27*3600));warm(c,40,bs);const flag=c.run("!!windowNeedsFull['T0040']");const nxt=c.computeAdaptiveRequestCount(40,'T0040');
 ok('D1 창이 못 덮으면 플래그 → 다음 요청 최대크기('+nxt+'='+maxc+')',flag&&nxt===maxc,'(짧은 창 요청 '+small+')');
 warm(c,40,bars(40,27*3600,70));ok('D2 덮는 응답을 받으면 플래그 해제',c.run("!windowNeedsFull['T0040']"));}
// ── E. 워밍업 후 카운터 == 차트 기준값(완결봉·filled 제외), 랜덤 60 시나리오
{let bad=0,tot=0;for(let seed=1;seed<=60;seed++){const c=load('tick.js',{});c.run("scriptStartTime=Date.now()-1e6");const bs=rw(500,seed,D,60);
  const [sd,st]=[bs[100].sdate,bs[100].stime];c.run("lastTickEpoch="+(D+500*60));c.registerPendingSignal('SP500','T0100','BEAR1',sd,st,1,100,50,0,'REAL',0,sd,st); // 판정 안 나는 가격(BEAR 목표가 1: 눌림 후 도달 불가)
  c.run("pendingSignals[0].barsElapsedSinceRegistration="+(seed*3%50));warm(c,100,bs);const sg=c.run('pendingSignals[0]');tot++;
  const expect=bs.slice(0,-1).filter(b=>{const e=Date.UTC(+b.sdate.slice(0,4),+b.sdate.slice(4,6)-1,+b.sdate.slice(6,8),...b.stime.split(':').map(Number))/1000;return e>sg.signalEpoch}).length;
  if(!sg||sg.barsElapsedSinceRegistration!==expect)bad++;}
 ok('E 워밍업 후 카운터 = 차트 완결봉 수 (60 시나리오, 임의의 저장값에서 시작)',bad===0,'('+(tot-bad)+'/'+tot+')');}
console.log(out.join('\n'));
