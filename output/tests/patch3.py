import re
def rep(t,old,new,n=1,label=''):
    c=t.count(old); assert c==n,f"[{label}] expected {n}, got {c}: {old[:90]!r}"; return t.replace(old,new)

NEW_BLOCK = r'''// ---------------------------------------------------------------------------------
// [신규][2026-09-30][v5.17 차트봉 카운트를 단일 기준값으로 통일 + 불일치 원인 진단]
// 기준값 = "신호 시각 이후의 차트 완결봉 수(마지막 봉 제외, filled 제외)". 실제 차트와 0.2~1.3% 내로 맞는 것을 알림 실측(1160/1162,
// 327/330, 1263/1280)으로 확인. 이 값을 (1)워밍업 재판정의 26봉 게이트, (2)판정사유 표시(gate=N/26), (3)게이트 신뢰성 검사,
// (4)실시간 판정의 게이트 카운터(워밍업마다 이 값으로 덮어씀), (5)재조회 창 크기(오래된 신호를 못 덮으면 다음 요청을 최대 크기로)
// 에 일괄 적용한다. 실시간이 센 봉수는 워밍업 사이 구간의 임시값일 뿐이며 다음 워밍업에서 항상 기준값으로 교정된다.
// 재동기화 직전 값(실시간이 센 값)과 기준값이 2 이상 다르면(단, 같은 실행 중 직전 동기화가 있었던 신호만) GATE_COUNT_SYNC 줄로
// 원인 판별용 수치를 남긴다. 재시작 직후 첫 동기화(꺼진 시간분/이전 누적 오차)는 진단로그에만 남기고 알림은 내지 않는다.
var GATE_SYNC_MIN_DIFF = 2;            // 이 이상 차이날 때만 기록(경계 1봉 흔들림은 무시)
var GATE_SYNC_LOG_COOLDOWN_SEC = 600;  // 같은 신호는 10분에 한 번만 기록
var liveReseedStats = {};              // 프레임 -> { n: 실시간 빌더 재시작 횟수, discarded: 버려진 부분봉 틱수(틱봉), gap: 무틱공백 정지 횟수(분봉) }
var gateSyncBase = {};                 // 신호키 -> 이번 실행의 직전 동기화 시점 기준값(저장 안 함: 재시작하면 첫 동기화는 기록만)
var windowNeedsFull = {};              // 프레임 -> true: 재조회 창이 가장 오래된 감시신호를 못 덮음 -> 다음 요청은 최대 크기로
var windowUncoverableLoggedAt = {};    // 프레임 -> 마지막 기록시각(ms) - 최대 크기로도 못 덮는 초장기 신호 진단로그 스팸 방지
function countRealBarsAfterEpoch(bars, epochRef) {
    if (epochRef === undefined || epochRef === null) return 0;
    var n = 0;
    for (var i = 0; i < bars.length; i++) {
        if (bars[i].filled) continue;
        if (dateTimeToEpochApprox(String(bars[i].sdate), bars[i].stime) > epochRef) n++;
    }
    return n;
}
function getLiveReseedStats(period) { return liveReseedStats[period] || (liveReseedStats[period] = { n: 0, discarded: 0, gap: 0 }); }
function logGateCountSync(sig, base, preCount, chartCnt) {
    var diff = chartCnt - preCount;
    if (Math.abs(diff) < GATE_SYNC_MIN_DIFF) return;
    var nowEp = lastTickEpoch || Math.floor(Date.now() / 1000);
    if (sig._syncLogEpoch !== undefined && sig._syncLogEpoch !== null && (nowEp - sig._syncLogEpoch) < GATE_SYNC_LOG_COOLDOWN_SEC) return;
    sig._syncLogEpoch = nowEp;
    var isTick = (sig.tf.charAt(0) === "T");
    var rs = getLiveReseedStats(sig.period);
    var liveD = (sig._liveBars || 0) - base.liveBars;          // 직전 동기화 이후 실시간이 완결시킨 봉 수
    var chartD = chartCnt - base.chartCnt;                      // 같은 구간에 차트에 생긴 봉 수
    var reseeds = rs.n - base.reseed, discarded = rs.discarded - base.discard, gaps = rs.gap - base.gap;
    var ticksD = isTick ? (totalTicksReceived - base.ticks) : 0;
    var expTicks = isTick ? chartD * sig.period : 0;
    var cause;
    if (diff > 0) {
        if (isTick && chartD >= 3 && ticksD < 0.8 * expTicks) cause = "TICK_SHORT";                         // 실시간 수신틱이 차트 기준보다 적음
        else if (!isTick && gaps > 0 && chartD - liveD >= 1) cause = "LIVE_GAP_STOP";                       // 무틱공백으로 실시간 정지
        else if (chartD - liveD >= 2 && reseeds > 0 && isTick && discarded >= sig.period * 0.5 * (chartD - liveD)) cause = "RESEED_LOSS"; // 재조회 때 실시간 빌더 재시작으로 손실
        else if (chartD - liveD >= 2) cause = "LIVE_BAR_MISSED";                                            // 실시간이 봉을 놓침(원인 미상)
        else cause = "COUNTER_LOW_OTHER";                                                                   // 구간 봉수는 맞는데 카운터가 작음(기타)
    } else {
        cause = "LIVE_OVERCOUNT";                                                                            // 실시간이 차트보다 봉을 더 셈
    }
    var detail = "sig=" + sig.sdate + " " + sig.stime + "@" + Number(sig.price).toFixed(2) +
        "|liveD=" + liveD + "|chartD=" + chartD + "|pre=" + preCount + "|reseed=" + reseeds +
        (isTick ? ("|discard=" + discarded + "|ticks=" + ticksD + "|expTicks=" + expTicks) : ("|gap=" + gaps));
    try {
        logDiagnostic("[DIAG][GATE_COUNT_SYNC] label=" + sig.tf + " kind=" + sig.kind + " live=" + preCount + " chart=" + chartCnt + " cause=" + cause + " " + detail);
        var wp = nowServerTimeStr().split(" ");
        timedPrintOnFile(OUTPUT_FILE, sig.itemName + "," + sig.tf + ",GATE_COUNT_SYNC," + wp[0] + "," + wp[1] + "," + sig.kind + "," + preCount + "," + chartCnt + "," + cause + "," + detail + "\n");
    } catch (eLog) {}
}
function syncGateCounter(sig, completedBars, preWalkCount) {
    var chartCnt = countRealBarsAfterEpoch(completedBars, sig.signalEpoch);
    var pk = pkOf(sig), rs = getLiveReseedStats(sig.period);
    var base = gateSyncBase[pk];
    try {
        if (base) logGateCountSync(sig, base, preWalkCount, chartCnt);
        else if (Math.abs(chartCnt - preWalkCount) >= GATE_SYNC_MIN_DIFF)
            logDiagnostic("[DIAG][GATE_COUNT_SYNC_INIT] label=" + sig.tf + " kind=" + sig.kind + " saved=" + preWalkCount + " chart=" + chartCnt + " diff=" + (chartCnt - preWalkCount) + " (재시작 후 첫 동기화: 꺼진 시간분/이전 누적 오차 포함, 알림 없음)");
    } catch (eSync) {}
    sig.barsElapsedSinceRegistration = chartCnt; // 기준값으로 덮어씀(올리기/내리기 모두)
    gateSyncBase[pk] = { chartCnt: chartCnt, liveBars: sig._liveBars || 0, ticks: (typeof totalTicksReceived !== "undefined" ? totalTicksReceived : 0), reseed: rs.n, discard: rs.discarded, gap: rs.gap };
}
function windowCoversOldestSignal(fileLabel, bars) {
    var oldest = oldestPendingSignalEpoch(fileLabel);
    if (oldest === null || bars.length === 0) return true;
    return dateTimeToEpochApprox(String(bars[0].sdate), bars[0].stime) <= oldest;
}
'''

def patch(t,tick):
    # 1) replace the v5.16 block (from its header comment to the end of syncGateCounter) with the v5.17 block
    i=t.index('// ---------------------------------------------------------------------------------\n// [신규][2026-09-30][v5.16')
    j=t.index('function syncGateCounter(')
    j=t.index('\n}\n',j)+3
    t=t[:i]+NEW_BLOCK+t[j:]
    # 2) remove per-signal diagnostic fields that bloat the persisted JSON
    t=re.sub(r'\n        _liveStartEpoch: \(typeof lastTickEpoch.*?\n        _reseedN0:[^\n]*\n','\n',t,count=1,flags=re.S)
    assert '_liveStartEpoch' not in t and '_reseedN0' not in t
    t=t.replace('            sig._warmAdds = (sig._warmAdds || 0) + 1;\n','')
    assert '_warmAdds' not in t
    # 3) resolveHistorically: chart-based counter as the reference value
    t=rep(t,'    var startBarIndex = findFirstBarIndexAtOrAfterEpoch(bars, sigEpochCached);\n','    var startBarIndex = findFirstBarIndexAtOrAfterEpoch(bars, sigEpochCached);\n    // [신규][v5.17] 재조회 창이 신호 시점을 덮으면, 이 봉 시점까지 센 차트 완결봉 수(trueBarCountAsOfThisBar)를 영속 카운터에도 그대로 기록 -\n    // 판정사유(gate=N/26)/게이트 신뢰성 검사/실시간 게이트가 전부 같은 기준값을 본다. 못 덮으면(창이 짧음) 기존 커서 방식 유지.\n    var windowCovers = (bars.length > 0 && dateTimeToEpochApprox(String(bars[0].sdate), bars[0].stime) <= sigEpochCached);\n',1,'covers')
    t=rep(t,'        if (barEpoch > judgedFromEpoch) { sig.lastJudgedBarEpoch = barEpoch; judgedFromEpoch = barEpoch; }\n','        if (barEpoch > judgedFromEpoch) { sig.lastJudgedBarEpoch = barEpoch; judgedFromEpoch = barEpoch; }\n        if (windowCovers) sig.barsElapsedSinceRegistration = trueBarCountAsOfThisBar;\n',1,'setcounter')
    # 4) pending pass + trial use completed bars only; sync with completed bars
    t=rep(t,'        runPendingResolutionPass(\n            function (rsig) { return rsig.tf === thisFileLabel; },','        var completedBars = bars.slice(0, Math.max(0, bars.length - 1)); // [v5.17] 형성중일 수 있는 마지막 봉은 재판정/카운트 기준에서 제외(실시간 틱이 담당)\n        runPendingResolutionPass(\n            function (rsig) { return rsig.tf === thisFileLabel; },',1,'completed')
    t=rep(t,'                    var rResult = resolveHistorically(rsig, bars);\n','                    var rResult = resolveHistorically(rsig, completedBars);\n',1,'pass')
    t=rep(t,'syncGateCounter(rsig, bars, _cntPre);','syncGateCounter(rsig, completedBars, _cntPre);',1,'sync call')
    # 5) coverage guarantee
    cov='''        // [신규][v5.17] 재조회 창이 이 프레임의 가장 오래된 감시신호를 못 덮으면(수신속도 추정 오차 등) 카운터 동기화와 안전망 재판정이
        // 건너뛰어지므로, 다음 요청을 최대 크기로 받게 한다. 최대 크기로도 못 덮는 초장기 신호는 진단로그만 남기고 포기한다.
        try {
            if (windowCoversOldestSignal(thisFileLabel, bars)) { delete windowNeedsFull[thisFileLabel]; }
            else if (thisReqCount < %s) { windowNeedsFull[thisFileLabel] = true; }
            else {
                delete windowNeedsFull[thisFileLabel];
                if (!windowUncoverableLoggedAt[thisFileLabel] || (Date.now() - windowUncoverableLoggedAt[thisFileLabel]) > 3600000) {
                    windowUncoverableLoggedAt[thisFileLabel] = Date.now();
                    logDiagnostic("[DIAG][WINDOW_NOT_COVERING] label=" + thisFileLabel + " 요청=" + thisReqCount + " - 최대 크기로도 가장 오래된 감시신호(" + oldestPendingSignalEpoch(thisFileLabel) + ")를 못 덮음(카운터 동기화 불가)");
                }
            }
        } catch (eCov) {}
'''
    if tick:
        t=rep(t,'        var barsForCalc = bars.slice(0, Math.max(0, bars.length - 1));\n',cov%'computeRequestCount(thisCycle)'+'        var barsForCalc = completedBars;\n',1,'cov tick')
        t=rep(t,'    var originalMax = computeRequestCount(cycle);\n','    var originalMax = computeRequestCount(cycle);\n    if (windowNeedsFull[fileLabel]) return originalMax; // [v5.17] 직전 응답이 가장 오래된 감시신호를 못 덮음 -> 최대 크기\n',1,'adaptive tick')
    else:
        t=rep(t,'        var calc = new SignalCalculator();\n        var signals = [];',cov%'MAX_BAR_COUNT'+'        var calc = new SignalCalculator();\n        var signals = [];',1,'cov min')
        t=rep(t,'                    var trialResult = resolveHistorically(trialSig, bars);','                    var trialResult = resolveHistorically(trialSig, completedBars);',1,'trial min')
        t=rep(t,'    if (adaptiveCount === null) return Math.min(MAX_BAR_COUNT, Math.max(originalMax, coverageFloor));','    if (windowNeedsFull[fileLabel]) return Math.min(MAX_BAR_COUNT, Math.max(originalMax, coverageFloor)); // [v5.17] 직전 응답이 가장 오래된 감시신호를 못 덮음 -> 최대 크기\n    if (adaptiveCount === null) return Math.min(MAX_BAR_COUNT, Math.max(originalMax, coverageFloor));',1,'adaptive min')
    # 6) prune per-signal sync baselines
    t=rep(t,'    Object.keys(pretty2Written).forEach(function (k) { if (pretty2Written[k].epoch < cutoff) delete pretty2Written[k]; });\n','    Object.keys(pretty2Written).forEach(function (k) { if (pretty2Written[k].epoch < cutoff) delete pretty2Written[k]; });\n    var _pkSet = {}; pendingSignals.forEach(function (s) { _pkSet[pkOf(s)] = true; }); Object.keys(gateSyncBase).forEach(function (k) { if (!_pkSet[k]) delete gateSyncBase[k]; });\n',1,'prune')
    t=rep(t,'var QUIET_DIAG_TAGS = ["[DIAG][GATE_COUNT_SYNC]",','var QUIET_DIAG_TAGS = ["[DIAG][GATE_COUNT_SYNC]", "[DIAG][GATE_COUNT_SYNC_INIT]", "[DIAG][WINDOW_NOT_COVERING]",',1,'quiet')
    return t

HIST='''// [2026-09-30][v5.17 - 차트봉 카운트를 단일 기준값으로 통일] 사용자 실측: 알림의 차트 카운트(1160/327/1263)가 실제 차트(1162/330/1280)와 0.2~1.3% 내로 일치,
//   실시간이 센 값(82/277/1060)은 크게 어긋남 -> 차트 완결봉 수(마지막 봉/filled 제외)를 모든 기능의 기준값으로 사용.
//   (1)워밍업 재판정이 창이 신호를 덮을 때 영속 카운터를 차트 기준 봉수로 직접 기록 - 26봉 게이트/판정사유(gate=N/26)/게이트 신뢰성 검사가 같은 값을 봄
//      (예전엔 판정사유에 "gate=13/26"처럼 커서 방식 값이 찍혀 달성인데 26 미만으로 보였음).
//   (2)워밍업 재판정/분봉 즉시판정은 완결봉만 사용(마지막 봉은 형성중일 수 있어 실시간 틱이 담당).
//   (3)재조회 창이 가장 오래된 감시신호를 못 덮으면 다음 요청을 최대 크기로 받음(수신속도 추정 오차로 동기화가 건너뛰어지던 구멍).
//   (4)진단: 재시작 후 첫 동기화는 진단로그(GATE_COUNT_SYNC_INIT)에만 남기고, 같은 실행의 이후 동기화에서 2 이상 어긋나면 GATE_COUNT_SYNC(알림).
'''
for name,tick in (('tick',True),('min',False)):
    t=open(f'v516_{name}.js',encoding='utf-8').read()
    t=patch(t,tick)
    L=t.split('\n'); assert 'v5.16(' in L[1]; L[1]=L[1].replace('v5.16(','v5.17('); L.insert(2,HIST.rstrip('\n'))
    open(f'{name}.js','w',encoding='utf-8').write('\n'.join(L))
print('scripts patched')
