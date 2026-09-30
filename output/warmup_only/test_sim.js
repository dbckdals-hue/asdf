// 가짜 예스스팟 엔진으로 워밍업 전용 스크립트 검증 (타이머/응답 시뮬레이션, 가상시계)
const vm=require('vm'),fs=require('fs');
function run(file,{timeoutSet=[],lateSet=[],failSet=[],latency=()=>200,maxPasses=2}={}){
  let now=1e12;const timers={};const logs=[];const reqs=[];let removed=0;const alive=new Set();let maxAlive=0;
  class FD extends Date{constructor(...a){a.length?super(...a):super(now)}static now(){return now}}
  let respQueue=[]; // {at, obj}
  const ctx={Date:FD,console,Math,Number,Array,isFinite,
    CHART_PERIOD_TICK:1,CHART_PERIOD_MINUTE:2,CHART_REQCOUNT_BAR:1,
    ReqChartItem:function(code,cycle,period,count,kind){this.code=code;this.cycle=cycle;this.period=period;this.count=count;},
    IndicatorInfo:function(n){this.n=n},
    Main:{MessageLog:m=>logs.push(m),
      SetTimer:(id,ms)=>{timers[id]=now+ms},KillTimer:id=>{delete timers[id]},
      RemoveObject:o=>{if(!alive.has(o))throw new Error('double remove');alive.delete(o);removed++},
      ReqChartEx:(req,a,b)=>{ if(failSet.includes(req.cycle))return false;reqs.push(req);
        if(!timeoutSet.includes(req.cycle)){const o={cycle:req.cycle,n:req.count,GetHigh:(k,i)=>i<req.count-1?1:(i==req.count-1?1:null),GetLow:()=>1,GetSDate:()=>20260930,GetSTime:()=>0};
          const d=latency(req);respQueue.push({at:now+d,obj:o,cycle:req.cycle});}
        else if(lateSet.includes(req.cycle)){const o={GetHigh:()=>1};respQueue.push({at:now+15000,obj:o,cycle:req.cycle});}
        return true;}}};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(file,'utf8').replace(/var MAX_PASSES = \d+;/,'var MAX_PASSES = '+maxPasses+';'),ctx);
  ctx.Main_OnStart();
  for(let step=0;step<2000000;step++){
    // next event
    let next=Infinity,kind=null,key=null;
    for(const k in timers)if(timers[k]<next){next=timers[k];kind='t';key=k}
    respQueue.forEach((r,i)=>{if(r.at<next){next=r.at;kind='r';key=i}});
    if(next===Infinity)break;
    now=Math.max(now,next);
    if(kind==='t'){delete timers[key];ctx.Main_OnTimer(Number(key));}
    else{const r=respQueue.splice(key,1)[0];alive.add(r.obj);maxAlive=Math.max(maxAlive,alive.size);ctx.Main_OnRcvChartEx(r.obj);}
  }
  return {logs,reqs,removed,alive:alive.size,maxAlive,elapsed:now-1e12};
}
const out=[];const ok=(n,c,e)=>out.push((c?'PASS ':'FAIL ')+n+(e?'  '+e:''));
for(const [f,n,first,last] of [['1an_nasdaq_tick_warmup_only.txt',195,30,1000],['1an_nasdaq_min_warmup_only.txt',110,1,110]]){
  const r=run(f);const fin=r.logs.filter(l=>/바퀴 완료/.test(l));
  ok(f+' 2바퀴, 프레임 '+n+'개 순서대로 요청',r.reqs.length===2*n&&r.reqs[0].cycle===first&&r.reqs[n-1].cycle===last&&r.reqs[n].cycle===first);
  ok(f+' 요약 2회, 합계 성공+타임아웃+실패='+n,fin.length===2&&fin.every(l=>new RegExp('= '+n+' / '+n).test(l)),fin[0].slice(0,120));
  ok(f+' 객체 전부 삭제(남은 것 0), 동시에 살아있는 최대 '+r.maxAlive,r.alive===0&&r.removed===2*n);
  console.log('   200ms 응답일 때 1바퀴 약',(r.elapsed/2/1000).toFixed(0)+'초 (가상시계)');
  const t=run(f,{timeoutSet:[first+5*(f.includes('tick')?1:1)],failSet:[last]});
  const tf=t.logs.filter(l=>/바퀴 완료/.test(l));
  ok(f+' 타임아웃1+요청실패1 -> 합계 여전히 '+n,tf.length===2&&tf.every(l=>new RegExp('= '+n+' / '+n).test(l)&&/타임아웃 1/.test(l)&&/요청실패 1/.test(l)),tf[0].slice(0,140));
  const L=run(f,{timeoutSet:[first+5],lateSet:[first+5],maxPasses:1});
  ok(f+' 지각응답도 객체 삭제(누수 0)',L.alive===0,'남은객체 '+L.alive);
}
console.log(out.join('\n'));
