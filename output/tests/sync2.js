const {load,fmt}=require('./h2.js');
// ── 테스트 2: 정상 운영(2번째 이후 순환)의 재조회 창이 오래된 감시신호까지 덮는가? 못 덮으면 재동기화가 아예 건너뛰어짐 ──
const NOW=Date.UTC(2026,8,30,0,0,0)/1000, AGE_H=27, CHART_RATE=70/60; // 골드 진짜 틱속도 70틱/분 가정
function need(cyc){return Math.ceil(AGE_H*3600*CHART_RATE/cyc)+2}
console.log('신호 나이 '+AGE_H+'시간, 실제 거래속도 초당 '+CHART_RATE.toFixed(2)+'틱. "필요봉"=신호 시점까지 덮는 데 필요한 봉 수');
console.log('스크립트 가동시간 / 실시간 수신속도(실제 대비) → 창이 신호를 덮는 프레임 / 검사한 프레임');
for(const [elapsedMin,ratio] of [[60,1.0],[60,0.5],[10,1.0],[10,0.5],[240,0.7]]){
  let cover=0,tot=0,fail=[];
  for(const cyc of [35,40,60,70,100,130,155,320,785]){
    const c=load('tick.js',{});const lab='T'+String(cyc).padStart(4,'0');
    c.run("scriptStartTime=Date.now()-"+(elapsedMin*60000)+";lastTickEpoch="+NOW+";totalTicksReceived="+Math.round(elapsedMin*60*CHART_RATE*ratio)+";");
    const [sd,st]=fmt(NOW-AGE_H*3600);c.registerPendingSignal('SP500',lab,'BEAR1',sd,st,4990,cyc,50,0,'REAL',0,sd,st);
    c.run("lastCycleBarInfo['"+lab+"']={newestEpoch:"+(NOW-300)+"}");   // 이미 한 번 돈 뒤(정상 운영)
    const win=c.computeAdaptiveRequestCount(cyc,lab);tot++;if(win>=need(cyc))cover++;else fail.push('T'+cyc+'('+win+'<'+need(cyc)+')');}
  console.log('가동 '+String(elapsedMin).padStart(3)+'분 / 수신속도 '+(ratio*100)+'% → '+cover+'/'+tot+'  못 덮는 프레임: '+(fail.join(' ')||'없음'));}
