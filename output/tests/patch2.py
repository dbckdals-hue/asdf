import re
def rep(t,old,new,n=1,label=''):
    c=t.count(old); assert c==n,f"[{label}] expected {n}, got {c}: {old[:80]!r}"; return t.replace(old,new)

SYNC_FUNCS = r'''
// ---------------------------------------------------------------------------------
// [신규][2026-09-30][v5.16 게이트 카운터 차트기준 재동기화 + 불일치 원인 진단]
// 워밍업(차트 재조회)이 감시신호의 봉 카운터를 "신호 이후 차트 완결봉 수"로 다시 맞춘다(올리기만 하던 것을
// 내리기도 함). 마지막 봉은 형성중일 수 있어 제외(보수적: 게이트가 일찍 열리는 일은 없고 최악 1봉 늦음).
// 재동기화 직전의 카운터(실시간이 센 값)와 차트값이 2 이상 다르면, 어디서 구멍이 났는지 가릴 수 있는 수치를
// 함께 신호파일(GATE_COUNT_SYNC)과 진단로그에 남긴다 - 브릿지/대시보드 알림창에 한 줄로 표시된다.
var GATE_SYNC_MIN_DIFF = 2;            // 이 이상 차이날 때만 기록(경계 1봉 흔들림은 무시)
var GATE_SYNC_LOG_COOLDOWN_SEC = 600;  // 같은 신호는 10분에 한 번만 기록
var liveReseedStats = {};              // 프레임 -> { n: 실시간 빌더 재시작 횟수, discarded: 버려진 부분봉 틱수(틱봉), gap: 무틱공백 정지 횟수(분봉) }
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
function logGateCountSync(sig, preCount, postWalk, chartCnt, completedBars) {
    var diff = chartCnt - preCount;
    if (Math.abs(diff) < GATE_SYNC_MIN_DIFF) return;
    var nowEp = lastTickEpoch || Math.floor(Date.now() / 1000);
    if (sig._syncLogEpoch !== undefined && sig._syncLogEpoch !== null && (nowEp - sig._syncLogEpoch) < GATE_SYNC_LOG_COOLDOWN_SEC) return;
    sig._syncLogEpoch = nowEp;
    var isTick = (sig.tf.charAt(0) === "T");
    var rs = getLiveReseedStats(sig.period);
    var liveBars = sig._liveBars || 0, warmAdds = sig._warmAdds || 0;
    var reseeds = rs.n - (sig._reseedN0 || 0), discarded = rs.discarded - (sig._discard0 || 0), gaps = rs.gap - (sig._gap0 || 0);
    var chartInLive = 0;
    if (sig._liveStartEpoch !== undefined && sig._liveStartEpoch !== null) chartInLive = countRealBarsAfterEpoch(completedBars, sig._liveStartEpoch);
    var ticksIn = isTick ? (totalTicksReceived - (sig._ticks0 || 0)) : 0;
    var expTicks = isTick ? chartInLive * sig.period : 0;
    var cause;
    if (diff > 0) {
        if (isTick && chartInLive >= 3 && ticksIn < 0.8 * expTicks) cause = "TICK_SHORT";            // 실시간 시세 수신틱이 차트 기준보다 적음
        else if (chartInLive - liveBars >= 2 && reseeds > 0 && (isTick ? (discarded >= sig.period * 0.5 * (chartInLive - liveBars)) : true) && !(gaps > 0)) cause = "RESEED_LOSS"; // 재조회 때 실시간 빌더 재시작으로 손실
        else if (!isTick && gaps > 0 && chartInLive - liveBars >= 1) cause = "LIVE_GAP_STOP";        // 무틱공백으로 실시간 정지
        else if (chartInLive - liveBars >= 2) cause = "LIVE_BAR_MISSED";                              // 실시간이 봉을 놓침(원인 미상)
        else cause = "COUNTER_LOW_OTHER";                                                             // 실시간 봉수는 맞는데 카운터가 작음(초기값/기타)
    } else {
        cause = (postWalk - preCount >= 2) ? "WARM_OVERCOUNT" : "LIVE_OVERCOUNT";                    // 워밍업이 더 셈 / 실시간이 더 셈
    }
    var detail = "sig=" + sig.sdate + " " + sig.stime + "@" + Number(sig.price).toFixed(2) +
        "|live=" + liveBars + "|chartLive=" + chartInLive + "|warm=" + warmAdds + "|init=" + (sig._initCount || 0) +
        "|pre=" + preCount + "|post=" + postWalk + "|reseed=" + reseeds +
        (isTick ? ("|discard=" + discarded + "|ticks=" + ticksIn + "|expTicks=" + expTicks) : ("|gap=" + gaps));
    try {
        logDiagnostic("[DIAG][GATE_COUNT_SYNC] label=" + sig.tf + " kind=" + sig.kind + " live=" + preCount + " chart=" + chartCnt + " cause=" + cause + " " + detail);
        var wp = nowServerTimeStr().split(" ");
        timedPrintOnFile(OUTPUT_FILE, sig.itemName + "," + sig.tf + ",GATE_COUNT_SYNC," + wp[0] + "," + wp[1] + "," + sig.kind + "," + preCount + "," + chartCnt + "," + cause + "," + detail + "\n");
    } catch (eLog) {}
}
function syncGateCounter(sig, bars, preWalkCount) {
    var completed = bars.slice(0, Math.max(0, bars.length - 1));
    var chartCnt = countRealBarsAfterEpoch(completed, sig.signalEpoch);
    var postWalk = sig.barsElapsedSinceRegistration || 0;
    try { logGateCountSync(sig, preWalkCount, postWalk, chartCnt, completed); } catch (eSync) {}
    sig.barsElapsedSinceRegistration = chartCnt;
}
'''

def patch(t,tick):
    # helper block (replace the earlier standalone helper if present)
    m=re.search(r'function countRealBarsAfterEpoch\(bars, epochRef\) \{.*?\n\}\n',t,re.S)
    if m: t=t.replace(m.group(0),'',1)
    t=rep(t,'var pendingSignals = [];\n',SYNC_FUNCS+'var pendingSignals = [];\n',1,'funcs')
    # QUIET tag
    t=rep(t,'var QUIET_DIAG_TAGS = ["[DIAG][ACTUAL_COUNT]",','var QUIET_DIAG_TAGS = ["[DIAG][GATE_COUNT_SYNC]", "[DIAG][ACTUAL_COUNT]",',1,'quiet')
    # signal fields at creation
    t=rep(t,'registeredAt: Date.now(),','registeredAt: Date.now(),\n        _liveStartEpoch: (typeof lastTickEpoch !== "undefined" ? lastTickEpoch : null), _ticks0: totalTicksReceived, _liveBars: 0, _warmAdds: 0, _initCount: (' + ('initialBarsElapsed' if tick else '0') + ' || 0),\n        _reseedN0: getLiveReseedStats(period).n, _discard0: getLiveReseedStats(period).discarded, _gap0: getLiveReseedStats(period).gap,',1,'fields')
    # live bar counting
    if tick:
        t=rep(t,'            s.barsElapsedSinceRegistration = (s.barsElapsedSinceRegistration || 0) + 1;\n','            s.barsElapsedSinceRegistration = (s.barsElapsedSinceRegistration || 0) + 1;\n            s._liveBars = (s._liveBars || 0) + 1;\n',2,'livebars')
        t=rep(t,'            barsSinceSignal++;\n','            barsSinceSignal++;\n            sig._warmAdds = (sig._warmAdds || 0) + 1;\n',1,'warmadds')
        t=rep(t,'        liveBuilders[thisCycle] = new TickBarBuilder(thisCycle);','        var _oldLB = liveBuilders[thisCycle], _rsT = getLiveReseedStats(thisCycle); _rsT.n++; if (_oldLB && _oldLB.count) _rsT.discarded += _oldLB.count; // [진단] 재시작으로 버려지는 부분봉 틱수 집계\n        liveBuilders[thisCycle] = new TickBarBuilder(thisCycle);',1,'reseed')
        # sync in unresolved branch
        t=rep(t,'                    var rResult = resolveHistorically(rsig, bars);\n','                    var _cntPre = rsig.barsElapsedSinceRegistration || 0;\n                    var rResult = resolveHistorically(rsig, bars);\n',1,'pre')
        t=rep(t,'                            rsig.barsElapsedSinceRegistration = countRealBarsAfterEpoch(bars, rsig.signalEpoch);','                            syncGateCounter(rsig, bars, _cntPre);',1,'sync tick')
    else:
        t=rep(t,'            s.barsElapsedSinceRegistration = (s.barsElapsedSinceRegistration || 0) + barsAdvance;\n','            s.barsElapsedSinceRegistration = (s.barsElapsedSinceRegistration || 0) + barsAdvance;\n            s._liveBars = (s._liveBars || 0) + barsAdvance;\n',1,'livebars')
        t=rep(t,'            barsScannedSinceSignal++;\n','            barsScannedSinceSignal++;\n            sig._warmAdds = (sig._warmAdds || 0) + 1;\n',1,'warmadds')
        t=rep(t,'        delete liveCalcs[fileLabel];\n','        getLiveReseedStats(period).gap++; // [진단] 무틱공백으로 실시간 신규검색 정지한 횟수\n        delete liveCalcs[fileLabel];\n',1,'gap')
        t=rep(t,'        liveBuilders[thisFileLabel] = new MinuteBarBuilder(thisCycle);','        getLiveReseedStats(thisCycle).n++; // [진단] 실시간 빌더 재시작 횟수\n        liveBuilders[thisFileLabel] = new MinuteBarBuilder(thisCycle);',1,'reseed')
        t=rep(t,'                    var _b4 = ','                    var _cntPre = rsig.barsElapsedSinceRegistration || 0;\n                    var _b4 = ',1,'pre')
        t=rep(t,'''                        var _fb = bars.length > 0 ? dateTimeToEpochApprox(String(bars[0].sdate), bars[0].stime) : null;
                        if (_fb !== null && _fb <= rsig.signalEpoch) rsig.barsElapsedSinceRegistration = countRealBarsAfterEpoch(bars, rsig.signalEpoch);''','''                        var _fb = bars.length > 0 ? dateTimeToEpochApprox(String(bars[0].sdate), bars[0].stime) : null;
                        if (_fb !== null && _fb <= rsig.signalEpoch) syncGateCounter(rsig, bars, _cntPre);''',1,'sync min')
    return t

for name,tick in (('tick',True),('min',False)):
    t=open(f'v515/{name}.js',encoding='utf-8').read()
    # v5.15 tick has no helper yet -> patch handles both; ensure tick v5.15 still uses countBarsAfterEpoch block
    if tick:
        a='''                            var freshElapsed = countBarsAfterEpoch(bars, rsig.signalEpoch);
                            if (freshElapsed > (rsig.barsElapsedSinceRegistration || 0)) rsig.barsElapsedSinceRegistration = freshElapsed;'''
        t=rep(t,a,'                            rsig.barsElapsedSinceRegistration = countRealBarsAfterEpoch(bars, rsig.signalEpoch);',1,'tick base')
    else:
        a='''                    if (!rResult) {
                        // [수정][2026-09-29] 워밍업 재판정이'''
        t=rep(t,a,'''                    if (!rResult) {
                        var _fb = bars.length > 0 ? dateTimeToEpochApprox(String(bars[0].sdate), bars[0].stime) : null;
                        if (_fb !== null && _fb <= rsig.signalEpoch) rsig.barsElapsedSinceRegistration = countRealBarsAfterEpoch(bars, rsig.signalEpoch);
                        // [수정][2026-09-29] 워밍업 재판정이''',1,'min base')
    t=patch(t,tick)
    hist='''// [2026-09-30][v5.16 - 게이트 카운터 차트기준 재동기화 + 불일치 원인 진단] 판정/신호검색 로직은 변경 없음(수정 전후 회귀테스트 동일).
//   (1)워밍업이 감시신호의 봉 카운터를 "신호 이후 차트 완결봉 수(마지막 봉 제외)"로 다시 맞춤 - 예전엔 올리기만 했고(분봉은 아예 없음),
//      워밍업이 형성봉을 매번 더해 카운터가 부풀거나 실시간이 적게 세도 그대로 남아 게이트가 일찍/늦게 열렸음.
//   (2)재동기화 직전 카운터(실시간 값)와 차트값이 2 이상 다르면 GATE_COUNT_SYNC 줄(신호파일+진단로그)에 원인 판별용 수치를 기록:
//      실시간이 센 봉수/같은 구간 차트 봉수/워밍업 가산/실시간 빌더 재시작 횟수와 버려진 틱수/수신틱 대비 차트틱(틱봉)/무틱공백 정지(분봉).
//      브릿지가 알림창용 한글 문구를 만들고 대시보드가 저품질이관처럼 한 줄로 표시한다.
'''
    L=t.split('\n')
    L[1]=re.sub(r'v5\.15\(','v5.16(',L[1]); L.insert(2,hist.rstrip('\n'))
    open(f'{name}.js','w',encoding='utf-8').write('\n'.join(L))
print('scripts ok')
