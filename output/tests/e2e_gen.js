const fs=require('fs');const src=fs.readFileSync('dtest.js','utf8').split("scenario('D1")[0]+
"const L=scenario('D1',{cycle:100,chartTpm:100,feedTpm:50,passEvery:0,minutes:20});fs.writeFileSync('e2e_tick.txt',L.join('\\n')+'\\n');"+
"const src2=null;";
eval(src.replace(/const \{load,fmt,chart,lines\}=require\('.\/h2.js'\);/,"const {load,fmt,chart,lines}=require('./h2.js');"));
// 분봉도 1건
