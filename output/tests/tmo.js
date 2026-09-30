const {load,fmt,chart,rw}=require('./h2.js');
const f=process.argv[2];const c=load(f,{});const logs=[];c.Main.MessageLog=m=>logs.push(String(m));
c.run("scriptStartTime=Date.now()-1e6");
c.run("var T0=Date.UTC(2026,8,29,12,0,0)/1000");
c.run("baseTargetList=[{code:'ESZ26',nameEn:'SP500',cycle:30},{code:'ESZ26',nameEn:'SP500',cycle:35},{code:'ESZ26',nameEn:'SP500',cycle:40}];targetList=baseTargetList;currentIndex=0;");
const bars=rw(300,5,Date.UTC(2026,8,29,12,0,0)/1000,10);
for(let i=0;i<3;i++){
  c.run("lastRemoveObjectAt=0;pendingRemoveObjects=[]");c.processNext();                    // 요청 전송
  const cyc=[30,35,40][i];
  if(cyc===35){c.Main_OnTimer(2);}    // 응답 안 옴 -> 타임아웃
  else{c.run("lastTickEpoch="+(Date.UTC(2026,8,29,12,0,0)/1000+3000));c.Main_OnRcvChartEx(chart(bars));}

}
c.run("lastRemoveObjectAt=0");c.processNext();
console.log(logs.join("\n"));console.log("idx",c.run("currentIndex"),"filled",c.run("Object.keys(filledCycles)"),"completed",c.run("Object.keys(completedCycles)"),"retryQ",c.run("retryQueue.length"),"degr",c.run("Object.keys(degradedPeriods)"),"passes",c.run("totalPassesCompleted"));
