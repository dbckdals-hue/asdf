import re,sys
def rep(t,old,new,n=1,label=''):
    c=t.count(old)
    assert c==n,f"[{label}] expected {n} match, got {c}: {old[:70]!r}"
    return t.replace(old,new)
def cut(t,start,end,new,label=''):
    i=t.index(start); assert t.count(start)==1,label+' start not unique'
    j=t.index(end,i); return t[:i]+new+t[j:]

def patch_script(t,tick):
    # ---- #4 PRETTY2 dedupe
    old=t[t.index('function writePretty2Events('):]
    old=old[:old.index('\n}\n')+3]
    new='''// [수정][2026-09-29][PRETTY2 중복기록 방지] 워밍업 재생은 매 순환마다 재조회 구간 전체를 다시
// 돌려서 이미 기록한 과거 신호의 PRETTY2_CONFIRMED를 매번 다시 만들어냈다(파일/방송 폭증 원인).
// 같은 신호키에 같은 내용(확정여부+케이스)이면 다시 쓰지 않고, 내용이 달라졌을 때만 다시 쓴다.
// 기록 키는 신호 날짜 기준 DEDUP_RETENTION_SEC(7일)이 지나면 pruneDedupStructures가 정리한다.
var pretty2Written = {}; // key -> { v: "확정|케이스", epoch }
function writePretty2Events(itemName, fileLabel, events) {
    if (!events || events.length === 0) return;
    var lines = [];
    events.forEach(function (ev) {
        var val = (ev.confirmed ? "1" : "0") + "|" + (ev.cases && ev.cases.length ? ev.cases.join("|") : "");
        var key = itemName + "|" + fileLabel + "|" + ev.kind + "|" + ev.sdate + "|" + ev.stime + "|" + Number(ev.price).toFixed(2);
        var prev = pretty2Written[key];
        if (prev && prev.v === val) return; // 이미 같은 내용을 기록함
        pretty2Written[key] = { v: val, epoch: dateTimeToEpochApprox(String(ev.sdate), ev.stime) };
        lines.push(itemName + "," + fileLabel + ",PRETTY2_CONFIRMED," + ev.sdate + "," + ev.stime + "," + Number(ev.price).toFixed(2) + "," + ev.kind + "," + (ev.confirmed ? "1" : "0") + "," + (ev.cases && ev.cases.length ? ev.cases.join("|") : ""));
    });
    writeLinesToFile(lines);
}
'''
    t=t.replace(old,new,1)
    t=rep(t,'    var cutoff = lastTickEpoch - DEDUP_RETENTION_SEC;\n','    var cutoff = lastTickEpoch - DEDUP_RETENTION_SEC;\n    Object.keys(pretty2Written).forEach(function (k) { if (pretty2Written[k].epoch < cutoff) delete pretty2Written[k]; });\n',1,'prune')
    # ---- #5 gate-closed history spam
    for cmp_,curr in (('<',''),):
        pass
    t=rep(t,'''if (sig.state === "WAITING" && curPrice < sig.price) { sig.state = "PULLBACK"; sig.pullbackWhen = whenStr; sig.pullbackPrice = curPrice; pushStateHistory(sig, whenStr, "PULLBACK_CONFIRMED", curPrice); }
            else if (sig.state === "PULLBACK" && curPrice > sig.price) { sig.state = "WAITING"; pushStateHistory(sig, whenStr, "WAITING", curPrice); }''',
'''if (sig.state === "WAITING" && curPrice < sig.price) { sig.state = "PULLBACK"; sig.pullbackWhen = whenStr; sig.pullbackPrice = curPrice; if (!sig._pullbackLogged) { sig._pullbackLogged = true; pushStateHistory(sig, whenStr, "PULLBACK_CONFIRMED", curPrice); } }
            else if (sig.state === "PULLBACK" && curPrice > sig.price) { sig.state = "WAITING"; } // [수정][2026-09-29] 게이트 닫힘 구간의 눌림<->대기 왕복은 이력을 무한히 늘리므로 상태값만 바꾸고 이력은 남기지 않는다(눌림확인은 신호당 첫 1회만 기록)''',1,'#5 bull')
    t=rep(t,'''if (sig.state === "WAITING" && curPrice > sig.price) { sig.state = "PULLBACK"; sig.pullbackWhen = whenStr; sig.pullbackPrice = curPrice; pushStateHistory(sig, whenStr, "PULLBACK_CONFIRMED", curPrice); }
            else if (sig.state === "PULLBACK" && curPrice < sig.price) { sig.state = "WAITING"; pushStateHistory(sig, whenStr, "WAITING", curPrice); }
        }
        return null;''',
'''if (sig.state === "WAITING" && curPrice > sig.price) { sig.state = "PULLBACK"; sig.pullbackWhen = whenStr; sig.pullbackPrice = curPrice; if (!sig._pullbackLogged) { sig._pullbackLogged = true; pushStateHistory(sig, whenStr, "PULLBACK_CONFIRMED", curPrice); } }
            else if (sig.state === "PULLBACK" && curPrice < sig.price) { sig.state = "WAITING"; }
        }
        return null;''',1,'#5 bear')
    if tick:
        t=rep(t,'        newSig.pullbackPrice = preWalkedSig.pullbackPrice;\n','        newSig.pullbackPrice = preWalkedSig.pullbackPrice;\n        newSig._pullbackLogged = preWalkedSig._pullbackLogged;\n',1,'#5 prewalk')
    # ---- #6 dirty marking only on real change
    t=rep(t,'            var result = applyPriceToSignal(sig, curPrice, curDateStr, curTimeStr, gateOpen, "updatePendingSignals(REAL)");\n',
'''            var _stBefore = sig.state, _hLenBefore = sig.stateHistory ? sig.stateHistory.length : 0;
            var result = applyPriceToSignal(sig, curPrice, curDateStr, curTimeStr, gateOpen, "updatePendingSignals(REAL)");
            // [수정][2026-09-29] 틱마다 모든 감시신호를 저장대상으로 표시하던 것을, 상태/이력이 실제로 바뀐 신호만 표시하도록 변경
            if (sig.state !== _stBefore || (sig.stateHistory ? sig.stateHistory.length : 0) !== _hLenBefore) excelMarkDirty(sig);
''',1,'#6 realtime')
    t=re.sub(r'        true // markDirtyOnKeep: 원래 keepPending이 매번 excelMarkDirty를 불렀음\(그대로 유지\)',
             '        false // markDirtyOnKeep: [수정][2026-09-29] 틱마다 전체 표시하던 것을 끄고, 실제 변경은 위 resolveFn에서 개별 표시',t,count=1)
    assert 'markDirtyOnKeep: [수정][2026-09-29]' in t
    t=rep(t,'''        try { Excel1.SetData(EXCEL_SHEET, excelShardCell(idx), JSON.stringify(arr)); didSomething = true; }''',
'''        var payload = JSON.stringify(arr);
        // [신규][2026-09-29] Excel 셀 글자수 한계(32,767자) 근접 경고 - 넘으면 저장 실패/잘림으로 재시작시 신호유실 위험
        if (payload.length > 30000) logMsg("!! [Excel저장] 샤드" + idx + " JSON " + payload.length + "자(" + arr.length + "개 신호) - 셀 한계(32767자) 근접/초과, 신호유실 위험");
        try { Excel1.SetData(EXCEL_SHEET, excelShardCell(idx), payload); didSomething = true; }''',1,'#6 payload')
    if tick:
        t=rep(t,'                    var rResult = resolveHistorically(rsig, bars);\n',
'''                    var _b4 = rsig.state + "|" + (rsig.barsElapsedSinceRegistration || 0) + "|" + (rsig.stateHistory ? rsig.stateHistory.length : 0) + "|" + rsig.lastAppliedBarEpoch + "|" + rsig.lastJudgedBarEpoch;
                    var rResult = resolveHistorically(rsig, bars);
''',1,'#6 warm before')
        t=rep(t,'''                        pendingStateDirty = true;
                        excelMarkDirty(rsig);
                        return false;''',
'''                        // [수정][2026-09-29] 카운터/상태/커서가 실제로 바뀐 경우에만 저장대상으로 표시(변화 없는 재조회마다 저장하던 것 제거)
                        var _af = rsig.state + "|" + (rsig.barsElapsedSinceRegistration || 0) + "|" + (rsig.stateHistory ? rsig.stateHistory.length : 0) + "|" + rsig.lastAppliedBarEpoch + "|" + rsig.lastJudgedBarEpoch;
                        if (_af !== _b4) { pendingStateDirty = true; excelMarkDirty(rsig); }
                        return false;''',1,'#6 warm after')
        # ---- #7 bar cache removal (tick only)
        t=cut(t,'var barHistoryCache = {};','function pkOf(sig)','// [삭제][2026-09-29] 봉캐시(barHistoryCache) 전체 제거 - 저장/복원/갱신만 하고 판정 어디서도 읽지 않던 죽은 기능(분봉은 v4.1에서 이미 제거됨)\n\n','#7 defs')
        t=cut(t,'        // [신규][2026-09-14][철회판정 안정성게이트용 봉값 추적]','        var calc = new SignalCalculator();\n','        // [삭제][2026-09-29] 봉캐시 갱신/저장 블록 제거\n','#7 block')
        t=cut(t,'        // [신규][2026-09-14] 봉캐시(barHistoryCache)도 완전초기화 대상에 포함','        for (var wi = 0; wi < EXCEL_SHARD_COUNT; wi++) {','','#7 reset')
        assert 'barHistoryCache' not in t.replace('barHistoryCache) 전체 제거','') , 'leftover barHistoryCache'
    else:
        # ---- 분봉 WARM 판정 결과(카운터/상태/커서 변경)도 틱봉처럼 저장대상으로 표시
        t=rep(t,'''                    var rResult = resolveHistorically(rsig, bars);
                    if (!rResult) return false;''',
'''                    var _b4 = rsig.state + "|" + (rsig.barsElapsedSinceRegistration || 0) + "|" + (rsig.stateHistory ? rsig.stateHistory.length : 0) + "|" + rsig.lastAppliedBarEpoch + "|" + rsig.lastJudgedBarEpoch;
                    var rResult = resolveHistorically(rsig, bars);
                    if (!rResult) {
                        // [수정][2026-09-29] 워밍업 재판정이 카운터/상태/커서를 바꿨는데 저장대상 표시가 없어 재시작시 옛 값으로 복원되던 것 수정(틱봉과 동일)
                        var _af = rsig.state + "|" + (rsig.barsElapsedSinceRegistration || 0) + "|" + (rsig.stateHistory ? rsig.stateHistory.length : 0) + "|" + rsig.lastAppliedBarEpoch + "|" + rsig.lastJudgedBarEpoch;
                        if (_af !== _b4) { pendingStateDirty = true; excelMarkDirty(rsig); }
                        return false;
                    }''',1,'#min warm dirty')
    return t
for name,tick in (('tick',True),('min',False)):
    src=open(f'orig/{name}.js',encoding='utf-8').read()
    open(f'{name}.js','w',encoding='utf-8').write(patch_script(src,tick))
    print(name,'patched')
# ---- bridge
b=open('orig/bridge_signals.py',encoding='utf-8').read()
b=rep(b,'disp=(\\d+);actual=(\\d+)','disp=(\\d+)[;_]actual=(\\d+)',1,'#9')
b=rep(b,'''    resolved_keys = set()
    for ln in lines:
        p = ln.split(",")
        if len(p) < 6:
            continue
        if p[2] in ("STATUS_ACHIEVED", "STATUS_INVALID"):
            resolved_keys.add((p[0], p[1], p[3], p[4]))
''','''    # [수정][2026-09-29][완전삭제 키충돌] 예전엔 (종목,타임프레임,날짜,시각)만으로 "판정 끝남"을 판단해서,
    # 같은 시각의 다른 신호(kind/가격이 다른)가 판정되면 아직 감시중인 신호까지 판정난 것으로 오인해
    # 지웠다. 이제 가격과 신호종류까지 포함해서 매칭한다.
    resolved_keys = set()        # (item,label,date,time,price,kind) - 판정줄 9번째 필드(신호종류)가 있는 경우
    resolved_nokind = set()      # (item,label,date,time,price) - 구버전 판정줄(9번째 필드 없음)
    resolved_any_kind = set()    # (item,label,date,time,price) - 부속줄(REGISTERED/SAVE_* 등) 매칭용
    stats_sig_keys = set()       # 일반 신호줄의 고유키(STATS_IMMEDIATE 이중집계 방지용)
    for ln in lines:
        p = ln.split(",")
        if len(p) < 6:
            continue
        if p[2] in ("STATUS_ACHIEVED", "STATUS_INVALID"):
            resolved_any_kind.add((p[0], p[1], p[3], p[4], p[5]))
            if len(p) >= 9 and p[8]:
                resolved_keys.add((p[0], p[1], p[3], p[4], p[5], p[8]))
            else:
                resolved_nokind.add((p[0], p[1], p[3], p[4], p[5]))
        elif p[2] in _SIGNAL_KINDS:
            stats_sig_keys.add(f"{p[1]}|{p[2]}|{p[3]}|{p[4]}|{p[5]}")
''',1,'#10 keys')
b=rep(b,'''        key = (item, label, date, time_)
        is_resolved = key in resolved_keys
''','''        if kind in ("STATUS_ACHIEVED", "STATUS_INVALID"):
            is_resolved = True
        elif kind in _SIGNAL_KINDS:
            is_resolved = ((item, label, date, time_, price, kind) in resolved_keys
                           or (item, label, date, time_, price) in resolved_nokind)
        else:
            is_resolved = (item, label, date, time_, price) in resolved_any_kind
''',1,'#10 is_resolved')
b=rep(b,'''                dedup_key = f"{label}|{signal_kind}|{date}|{time_}|{price}"
                if _merge_stats_immediate_into_archive(archive, label, stats_result, duration, dedup_key):
                    archive_changed = True''','''                dedup_key = f"{label}|{signal_kind}|{date}|{time_}|{price}"
                # [수정][2026-09-29] 같은 신호의 일반 줄이 이번에 같이 아카이브되면 그쪽에서 이미 집계되므로 건너뜀
                if dedup_key in stats_sig_keys:
                    pass
                elif _merge_stats_immediate_into_archive(archive, label, stats_result, duration, dedup_key):
                    archive_changed = True''',1,'#11 purge')
b=rep(b,'''        archive = _load_archive(path)
        archived_stats_immediate_keys = set(archive.get("_statsImmediateSeenKeys", []))''','''        archive = _load_archive(path)
        # [수정][2026-09-29][통계 이중집계 방지] 이 파일에 일반 신호줄이 이미 있는 신호는 STATS_IMMEDIATE로
        # (스크립트 재시작 후 재검출) 또 세지 않는다.
        signal_keys_live = set()
        for _ln in content.splitlines():
            _p = _ln.strip().split(",")
            if len(_p) >= 6 and _p[2] in _SIGNAL_KINDS:
                signal_keys_live.add(f"{_p[1]}|{_p[2]}|{_p[3]}|{_p[4]}|{_p[5]}")
        archived_stats_immediate_keys = set(archive.get("_statsImmediateSeenKeys", []))''',1,'#11 report a')
b=rep(b,'''                if dedup_key in archived_stats_immediate_keys or dedup_key in seen_stats_immediate_keys_live:
                    continue''','''                if dedup_key in signal_keys_live or dedup_key in archived_stats_immediate_keys or dedup_key in seen_stats_immediate_keys_live:
                    continue''',1,'#11 report b')
open('bridge_signals.py','w',encoding='utf-8').write(b);print('bridge patched')
