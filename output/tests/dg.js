const {load,lines}=require('./h2.js');
for(const f of ['tick.js','min.js']){
 const c=load(f,{});const logs=[];c.Main.MessageLog=m=>logs.push(String(m));c.run("scriptStartTime=Date.now()-1e6");
 const cyc=f==='tick.js'?[30,35,40]:[1,2,3];
 c.run("baseTargetList="+JSON.stringify(cyc.map(x=>({code:'ESZ26',nameEn:'SP500',cycle:x})))+";targetList=baseTargetList;currentIndex=0;");
 // 첫 요청(30)만 성공시키고 나머지 두 프레임은 계속 타임아웃 -> 재시도 소진 -> 저품질
 let guard=0;
 while(c.run("totalPassesCompleted")<1&&guard++<200){c.run("lastRemoveObjectAt=0;pendingRemoveObjects=[]");c.processNext();
   if(c.run("waitingForResponse")){ if(c.run("currentCycle")===cyc[0]&&guard<4){c.Main_OnRcvChartEx({GetHigh:(a,i)=>i<5?1:null,GetLow:()=>1,GetSDate:()=>20260930,GetSTime:()=>0,GetIndicatorData:()=>null});} else c.Main_OnTimer(2);}}
 const L=lines(c).filter(l=>l.split(',')[2]==='DEGRADED_DEFERRED');
 console.log(f,'순환',c.run("totalPassesCompleted"),'DEGRADED_DEFERRED 줄 수:',L.length,'\n  ',L.join('\n   '));
 console.log('  화면:',logs.filter(l=>/순환 완료/.test(l)).map(l=>l.replace(/^.*\] /,'')).join(''));
}
