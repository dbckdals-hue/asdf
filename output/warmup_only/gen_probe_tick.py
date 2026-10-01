BODY = r'''// ================================================================================
// [파일] GOLD(GCZ26) 틱봉 정렬 검증 프로브 | 실시간 틱으로 차트 틱봉을 정확히 재현할 수 있는지 측정
//  1) 시세구독으로 실시간 틱(가격,시각)을 COLLECT_SEC초(기본 150초) 동안 모은다
//  2) 그 뒤 같은 주기(CYCLE)의 차트를 요청해서 최근 완결봉들을 받는다
//  3) 모은 틱을 N틱씩 묶어(시작 위치 offset 0..N-1 전부 시도) 만든 봉이 차트 봉과 (시각,고가,저가)가 같은지 비교
//  결과: 가장 잘 맞는 offset과 일치율 -> 일치율이 ~100%면 "실시간 틱 = 차트 틱"이라 offset만 알면 정확히 이어붙일 수 있고,
//        낮으면 실시간 틱이 차트와 다르므로(누락/합쳐짐) 틱봉은 실시간 이어붙이기로는 정확할 수 없다.
//  엑셀/신호/파일 없음, 화면 로그만.
// ================================================================================
var MARKET_DATA_CODE = "GCZ26";
var CYCLE = 30;           // 검증할 틱봉 주기 (작을수록 짧은 시간에 비교할 봉이 많아짐)
var COLLECT_SEC = 150;    // 틱 수집 시간(초). 약 3분이면 끝남 (틱이 적은 시간대면 늘리세요)
var CHART_COUNT = 200;    // 차트에서 받을 봉 수
var TIMEOUT_MS = 20000;
var MAX_TICKS = 60000;

var ticks = [], waiting = false, pendingRemove = [], startMs = 0, lastProg = -1;
var RESULT_FILE = "C:\\dashboard\\data\\gold_tick_probe_result.txt"; // 결과 요약만 저장(몇 줄)
var resultBuf = [];
function logMsg(m) { Main.MessageLog("[GOLD 틱정렬프로브] " + m); resultBuf.push(m); }
function saveResult() { try { Main.PrintOnFile(RESULT_FILE, resultBuf.join("\n") + "\n"); resultBuf = []; Main.MessageLog("[GOLD 틱정렬프로브] 결과를 파일로 저장: " + RESULT_FILE); } catch (e) { Main.MessageLog("[GOLD 틱정렬프로브] 결과 파일 저장 실패: " + e.message); } }
function formatTime(rawTime) { var s = ("000000" + Math.floor(rawTime / 10000)).slice(-6); return s.slice(0, 2) + ":" + s.slice(2, 4) + ":" + s.slice(4, 6); }
function parseDateField(rawDate) { if (!rawDate || rawDate === 0) { var now = new Date(); return now.getFullYear() + ("0" + (now.getMonth() + 1)).slice(-2) + ("0" + now.getDate()).slice(-2); } return String(rawDate); }
function parseTimeField(rawTime) { if (rawTime === null || rawTime === undefined) return null; var n = Number(rawTime); if (n > 240000) n = Math.floor(n / 10000); var s = ("000000" + n).slice(-6); return s.slice(0, 2) + ":" + s.slice(2, 4) + ":" + s.slice(4, 6); }

var marketDataObj = null;
function Main_OnRcvMarketData(MarketData) { marketDataObj = MarketData; }
function Main_OnUpdateMarket(itemcode, updateID, exchangeKind) {
    if (!marketDataObj || itemcode !== MARKET_DATA_CODE || updateID !== 20001) return;
    var p = Number(marketDataObj.current);
    if (!isFinite(p) || p <= 0) return;
    var sd = parseDateField(marketDataObj.date), st = parseTimeField(marketDataObj.time);
    if (!sd || !st) return;
    if (ticks.length < MAX_TICKS) ticks.push({ p: p, d: sd, t: st });
}
function Main_OnStart() {
    for (var k = 1; k <= 10; k++) { try { Main.KillTimer(k); } catch (e) {} }
    startMs = Date.now();
    logMsg("스크립트 시작됨 (v2: 1초 타이머 방식)");
    try { Main.PrintOnFile(RESULT_FILE, "[시작] 틱정렬프로브 시작 - 결과는 끝나면 이 파일에 이어서 저장됩니다\n"); } catch (eF) { logMsg("시작 파일 쓰기 실패: " + eF.message); }
    try { Main.ReqMarketData(MARKET_DATA_CODE, 0); logMsg("시세구독 시작 - " + COLLECT_SEC + "초 동안 틱 수집 후 " + CYCLE + "틱 차트와 비교합니다(약 " + Math.round(COLLECT_SEC / 60 + 0.5) + "분)"); } catch (e) { logMsg("시세구독 실패: " + e.message); }
    Main.SetTimer(3, 1000);
}
function sendChart() {
    try {
        var req = new ReqChartItem(MARKET_DATA_CODE, CYCLE, CHART_PERIOD_TICK, CHART_COUNT, CHART_REQCOUNT_BAR);
        var ok = Main.ReqChartEx(req, null, new Array(new IndicatorInfo("#주기")));
        logMsg("수집 틱 " + ticks.length + "개 / 차트 " + CYCLE + "틱 요청 보냄 (반환=" + ok + ")");
        if (!ok) return;
        waiting = true; Main.SetTimer(2, TIMEOUT_MS);
    } catch (e) { logMsg("요청 예외: " + e.message); }
}
function Main_OnRcvChartEx(chartEx) {
    pendingRemove.push(chartEx); Main.SetTimer(5, 300);
    if (!waiting) { logMsg("지각응답 무시"); return; }
    waiting = false; Main.KillTimer(2);
    try { analyze(chartEx); } catch (e) { logMsg("분석 예외: " + e.message); }
}
function avail(ch, i) { try { var h = ch.GetHigh(1, i); return !(h == null || h == undefined) && isFinite(Number(h)); } catch (e) { return false; } }
function analyze(ch) {
    var n = CHART_COUNT;
    if (!avail(ch, n - 1)) { var lo = 0, hi = n - 1; if (!avail(ch, 0)) { logMsg("차트 봉 없음"); return; } while (lo < hi) { var mid = Math.ceil((lo + hi) / 2); if (avail(ch, mid)) lo = mid; else hi = mid - 1; } n = lo + 1; }
    var ind = null; try { ind = ch.GetIndicatorData("#주기", 2, 0); } catch (e) {}
    logMsg("차트 수신 " + n + "봉, #주기=" + ind + " (요청 " + CYCLE + ")");
    // 최근 5봉 출력 (idx0 = 형성중인 마지막 봉)
    // 차트 완결봉(idx>=1)을 시각|고|저 키로 저장
    var map = {}, chartList = [];
    for (var i = n - 1; i >= 1; i--) {
        var key = ch.GetSDate(1, i) + " " + formatTime(ch.GetSTime(1, i)) + "|" + Number(ch.GetHigh(1, i)) + "|" + Number(ch.GetLow(1, i));
        map[key] = true; chartList.push(key);
    }
    var firstTickKey = ticks.length ? (ticks[0].d + " " + ticks[0].t) : "";
    // 수신틱 수 vs 차트 틱 수: 첫 틱 이후의 차트 완결봉 수 x CYCLE
    var chartBarsInRange = 0;
    for (var c = 0; c < chartList.length; c++) { if (chartList[c].split("|")[0] > firstTickKey) chartBarsInRange++; }
    logMsg("수신틱 " + ticks.length + "개 / 같은 구간 차트 완결봉 " + chartBarsInRange + "개 x " + CYCLE + " = " + (chartBarsInRange * CYCLE) + "틱 (비율 " + (chartBarsInRange ? (ticks.length / (chartBarsInRange * CYCLE) * 100).toFixed(1) : "?") + "%)");
    if (ticks.length < CYCLE * 5) { logMsg("판정 불가: 수집한 틱이 " + ticks.length + "개뿐(" + (CYCLE * 5) + "개 미만) - COLLECT_SEC를 늘려서 다시 실행하세요"); return; }
    // offset별 일치 검사
    var results = [];
    for (var o = 0; o < CYCLE; o++) {
        var total = 0, hit = 0;
        for (var j = o; j + CYCLE <= ticks.length; j += CYCLE) {
            var h = -1e18, l = 1e18;
            for (var q = j; q < j + CYCLE; q++) { if (ticks[q].p > h) h = ticks[q].p; if (ticks[q].p < l) l = ticks[q].p; }
            var last = ticks[j + CYCLE - 1];
            total++;
            if (map[last.d + " " + last.t + "|" + h + "|" + l]) hit++;
        }
        results.push({ o: o, hit: hit, total: total });
    }
    var rates = results.map(function (x) { return x.total ? x.hit / x.total : 0; }).sort(function (a, b) { return a - b; });
    var median = rates[Math.floor(rates.length / 2)];
    results.sort(function (a, b) { return b.hit - a.hit; });
    var best = results[0], rate = best.total ? best.hit / best.total : 0;
    var ties = []; for (var r = 0; r < results.length; r++) { if (results[r].hit === best.hit) ties.push(results[r].o); }
    logMsg("가장 잘 맞는 offset " + ties.slice(0, 6).join(",") + (ties.length > 6 ? "..." : "") + ": 일치 " + best.hit + "/" + best.total + " (" + (rate * 100).toFixed(1) + "%), 다른 offset 중앙값 " + (median * 100).toFixed(1) + "%");
    if (rate >= 0.9 && rate - median >= 0.3) logMsg("판정: 실시간 틱 = 차트 틱 (일치율 " + (rate * 100).toFixed(1) + "%) -> 시작 위치(offset)만 맞추면 정확히 이어붙일 수 있음" + (ties.length > 1 ? " (같은 초에 틱이 여러 개라 offset 후보 " + ties.length + "개 - 더 많은 봉으로 좁히면 됨)" : ""));
    else if (rate >= 0.5 && rate - median >= 0.2) logMsg("판정: 부분 일치(" + (rate * 100).toFixed(1) + "%) -> 실시간 틱이 차트 틱과 일부 다름(누락/합쳐짐). 정확한 이어붙이기는 불가");
    else logMsg("판정: 일치 거의 없음(" + (rate * 100).toFixed(1) + "%) -> 실시간 틱으로는 차트 틱봉을 재현할 수 없음");
    logMsg("끝");
    saveResult();
}
function Main_OnTimer(id) {
    if (id == 1) { Main.KillTimer(1); }
    else if (id == 2) { Main.KillTimer(2); if (waiting) { waiting = false; logMsg("차트 응답 타임아웃"); saveResult(); } }
    else if (id == 3) {
        var el = Math.round((Date.now() - startMs) / 1000);
        if (el >= COLLECT_SEC) { Main.KillTimer(3); sendChart(); return; }
        Main.SetTimer(3, 1000);
        if (el % 10 === 0 && el !== lastProg) { lastProg = el; logMsg("수집 중... 경과 " + el + "초 / " + COLLECT_SEC + "초, 지금까지 틱 " + ticks.length + "개" + (ticks.length === 0 ? " (틱이 0개면 시세구독이 안 되는 것)" : "")); }
    }
    else if (id == 5) { Main.KillTimer(5); var l = pendingRemove; pendingRemove = []; for (var i = 0; i < l.length; i++) { try { Main.RemoveObject(l[i]); } catch (e) {} } }
}
'''
open('1an_gold_tick_probe.txt','w',encoding='utf8',newline='').write(BODY)
