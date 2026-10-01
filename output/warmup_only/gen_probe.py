BODY = r'''// ================================================================================
// [파일] GOLD(GCZ26) 분봉 시각 확인용 프로브 | 소량(10봉)만 요청해서 시각/고가/저가를 화면에 찍고 끝남
//   엑셀/신호/파일 없음. 순서: 시세구독(기존 스크립트와 동일) -> 요청 3건을 차례로
//   A) 1분봉 10봉 (#주기 지표 포함 = 기존과 동일한 요청 형식)
//   B) 12분봉 10봉 (#주기 지표 포함)
//   C) 12분봉 10봉 (지표 없이)  <- A,B가 응답이 안 오면 형식 차이를 가리기 위한 비교용
// ================================================================================
var MARKET_DATA_CODE = "GCZ26";
var STEPS = [ { name: "A 1분봉(지표포함)", cycle: 1, ind: true }, { name: "B 12분봉(지표포함)", cycle: 12, ind: true }, { name: "C 12분봉(지표없음)", cycle: 12, ind: false } ];
var COUNT = 10, TIMEOUT_MS = 10000;
var stepIdx = 0, waiting = false, pendingRemove = [];

function logMsg(m) { Main.MessageLog("[GOLD 분봉프로브] " + m); }
function formatTime(rawTime) { var s = ("000000" + Math.floor(rawTime / 10000)).slice(-6); return s.slice(0, 2) + ":" + s.slice(2, 4) + ":" + s.slice(4, 6); }

function Main_OnStart() {
    for (var t = 1; t <= 10; t++) { try { Main.KillTimer(t); } catch (e) {} }
    try { Main.ReqMarketData(MARKET_DATA_CODE, 0); logMsg("시세구독 요청 " + MARKET_DATA_CODE); } catch (e) { logMsg("시세구독 실패: " + e.message); }
    stepIdx = 0;
    Main.SetTimer(1, 1000);
}
function sendStep() {
    if (stepIdx >= STEPS.length) { logMsg("끝"); return; }
    var st = STEPS[stepIdx];
    try {
        var req = new ReqChartItem(MARKET_DATA_CODE, st.cycle, CHART_PERIOD_MINUTE, COUNT, CHART_REQCOUNT_BAR);
        var ok = st.ind ? Main.ReqChartEx(req, null, new Array(new IndicatorInfo("#주기"))) : Main.ReqChartEx(req, null, null);
        logMsg(st.name + " 요청 보냄 (ReqChartEx 반환=" + ok + ")");
        if (!ok) { stepIdx++; Main.SetTimer(1, 500); return; }
        waiting = true;
        Main.SetTimer(2, TIMEOUT_MS);
    } catch (e) { logMsg(st.name + " 요청 예외: " + e.message); stepIdx++; Main.SetTimer(1, 500); }
}
function Main_OnRcvChartEx(chartEx) {
    pendingRemove.push(chartEx);
    var st = STEPS[stepIdx];
    if (!waiting) { logMsg("응답이 왔지만 기다리는 요청이 없음(지각응답)"); Main.SetTimer(5, 300); return; }
    waiting = false; Main.KillTimer(2);
    logMsg(st.name + " 응답 도착");
    for (var k = 0; k < 5; k++) {
        try { logMsg("   최근봉 -" + k + ": " + chartEx.GetSDate(1, k) + " " + formatTime(chartEx.GetSTime(1, k)) + "  고가 " + chartEx.GetHigh(1, k) + " 저가 " + chartEx.GetLow(1, k)); } catch (e) { logMsg("   읽기 실패: " + e.message); }
    }
    stepIdx++;
    Main.SetTimer(5, 300);
}
function Main_OnTimer(id) {
    if (id == 1) { Main.KillTimer(1); sendStep(); }
    else if (id == 2) { Main.KillTimer(2); if (waiting) { waiting = false; logMsg(STEPS[stepIdx].name + " 타임아웃(" + (TIMEOUT_MS / 1000) + "초 응답 없음)"); stepIdx++; Main.SetTimer(1, 500); } }
    else if (id == 5) {
        Main.KillTimer(5);
        var l = pendingRemove; pendingRemove = [];
        for (var i = 0; i < l.length; i++) { try { Main.RemoveObject(l[i]); } catch (e) {} }
        if (!waiting) Main.SetTimer(1, 500);
    }
}
'''
open('1an_gold_min_probe.txt','w',encoding='utf8',newline='').write(BODY)
