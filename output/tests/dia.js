const {load}=require('./h2.js');const out=[];const ok=(n,c,e)=>out.push((c?'PASS ':'FAIL ')+n+(e?'  '+e:''));
const r=require('./reg.js');const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
// 1) LEGACY=true 면 패치 전(pre521)과 결과 완전 동일
for(const k of ['min','tick']){const a=r.run('chk_leg_'+k+'.js'),b=r.run(k+'_pre521.js');ok('LEGACY=true -> 패치 전과 동일 ('+k+')',eq(a,b));}
// 2) 신기준 함수 단위
const c=load('min.js',{});c.run("scriptStartTime=Date.now()-1e6");
const P=(sa,sb,bull,lf,fr,sh)=>JSON.stringify(c.run('checkDiamondPurpleNew('+JSON.stringify(sa)+','+JSON.stringify(sb)+','+bull+','+lf+','+fr+','+sh+')'));
const mk=(n,v)=>Array(n).fill(v);
// BULL: 반대색 구름 = SA<SB (두께 sb-sa>0). index0 최신. 왼쪽 시작 2
const sb=mk(30,100);
let sa=mk(30,99);sa[1]=101; // 삼각형(index1) 외 전부 구름(두께1)
ok('보라: 평탄2+뾰족+왼쪽 8봉 전부 구름 -> 통과',JSON.parse(P(sa,sb,true,2,2,true)).ok);
ok('보라: 평탄1봉이면 탈락',!JSON.parse(P(sa,sb,true,2,1,true)).ok);
ok('보라: 뾰족 아니면 탈락',!JSON.parse(P(sa,sb,true,2,3,false)).ok);
let sa2=sa.slice();for(let i=2;i<7;i++)sa2[i]=100; // 왼쪽 8봉 중 5봉 두께0 -> 구름 3봉
ok('보라: 왼쪽 구름 3봉(<4)이면 탈락',!JSON.parse(P(sa2,sb,true,2,3,true)).ok);
let sa3=sa.slice();for(let i=2;i<6;i++)sa3[i]=100; // 구름 4봉
ok('보라: 왼쪽 구름 4봉이면 통과(얇은 두께도 OK)',JSON.parse(P(sa3,sb,true,2,3,true)).ok);
ok('보라: 두께가 아주 얇아도(0.01) 4봉이면 통과',JSON.parse(P(sa3.map((v,i)=>v===99?99.99:v),sb,true,2,3,true)).ok);
ok('BEAR 방향(구름 SA>SB)도 동일하게 판정',JSON.parse(P(sb.map(()=>101),sb.map(()=>100).map((v,i)=>i===1?102:v),false,2,3,true)).ok);
// leftStrict
ok('leftStrict: 왼쪽 6봉+평균두께 기준 이상이면 true',JSON.parse(P(sa,sb,true,2,2,true)).leftStrict===true);
ok('leftStrict: 왼쪽 구름 4봉뿐이면 false (흰색 자격 없음)',JSON.parse(P(sa3,sb,true,2,3,true)).leftStrict===false);
// 흰색
const W=(sa,sb,bull,ls)=>JSON.stringify(c.run('evalDiamondWhiteNew('+JSON.stringify(sa)+','+JSON.stringify(sb)+','+bull+','+ls+')'));
const sbW=mk(30,100);const saR=mk(30,99); // 오른쪽 8봉 전부 두께1
ok('흰색: leftStrict+오른쪽 8봉 구름 -> 확정, 케이스4',JSON.parse(W(saR,sbW,true,true)).matched&&JSON.parse(W(saR,sbW,true,true)).cases[0]===4);
ok('흰색: leftStrict=false면 오른쪽이 좋아도 불확정',!JSON.parse(W(saR,sbW,true,false)).matched);
let saR5=saR.slice();for(let i=0;i<3;i++)saR5[i]=100; // 오른쪽 구름 5봉
ok('흰색: 오른쪽 구름 5봉(<6)이면 불확정',!JSON.parse(W(saR5,sbW,true,true)).matched);
let saR6=saR.slice();for(let i=0;i<2;i++)saR6[i]=100; // 6봉
ok('흰색: 오른쪽 구름 6봉이면 확정',JSON.parse(W(saR6,sbW,true,true)).matched);
const saThin=mk(30,99.999);const sbT=mk(30,100);saThin.forEach((v,i)=>{if(i%2)saThin[i]=99.9985}); // 변화폭이 있어야 ATR>0
const rnd=[];for(let i=0;i<30;i++)rnd.push(100+((i*37)%11-5)*0.5);
ok('흰색: 두께가 ATR 기준보다 얇으면 불확정(보라는 통과 가능한 얇은 구름)',!JSON.parse(W(rnd.map((v,i)=>i<8?99.999:v),mk(30,100),true,true)).matched);
console.log(out.join('\n'));
