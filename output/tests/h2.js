const vm=require('vm'),fs=require('fs');
exports.load=function(file,store){
  store=store||{};const written=[];const st={saves:0,sets:0};
  const ctx={console,Date,Math,JSON,Object,Array,parseInt,parseFloat,isFinite,Number,String,
    Main:{MessageLog(){},PrintOnFile(p,c){written.push([p,c]);},SetTimer(){},KillTimer(){},ReqMarketData(){},ReqChartEx(){return true},RemoveObject(){}},
    Excel1:{SetData(s,c,v){store[c]=v;st.sets++;},GetData(s,c){return store[c]||""},Save(){st.saves++;}},
    ReqChartItem:function(){},IndicatorInfo:function(){},CHART_PERIOD_TICK:1,CHART_PERIOD_MINUTE:2,CHART_REQCOUNT_BAR:1};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
  ctx.__w=written;ctx.__st=st;ctx.__store=store;ctx.run=s=>vm.runInContext(s,ctx);return ctx;
};
exports.fmt=t=>{const d=new Date(t*1000);return [d.toISOString().slice(0,10).replace(/-/g,''),d.toISOString().slice(11,19)]};
exports.chart=function(bars){const n=bars.length;const g=i=>bars[n-1-i];
 return {GetHigh:(k,i)=>g(i).high,GetLow:(k,i)=>g(i).low,GetSDate:(k,i)=>Number(g(i).sdate),GetSTime:(k,i)=>{const [h,m,s]=g(i).stime.split(':').map(Number);return (h*10000+m*100+s)*10000},GetIndicatorData:()=>null}};
exports.rw=function(n,seed,t0,step){let x=seed,p=5000,b=[];const r=()=>{x=(x*1664525+1013904223)%4294967296;return x/4294967296};
 for(let i=0;i<n;i++){p+=Math.round((r()-0.5)*8)/4;const [sd,st]=exports.fmt(t0+i*step);b.push({high:p+r()*1.5,low:p-r()*1.5,sdate:sd,stime:st});}return b};
exports.lines=function(c){const out=[];c.__w.forEach(([p,t])=>t.split('\n').filter(Boolean).forEach(l=>out.push(l)));return out};
