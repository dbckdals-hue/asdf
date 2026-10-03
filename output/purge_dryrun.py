# -*- coding: utf-8 -*-
"""
purge_dryrun.py - 신호달성 완전삭제를 "복사본"에 미리 돌려서, 실제로 얼마나 줄어드는지 보여주는 점검 도구입니다.
원본 로그 파일은 읽기만 하고 절대 수정하지 않습니다(임시 폴더에 복사해서 계산 후 삭제).

사용법 (bridge_signals.py 가 있는 폴더, 보통 C:\\dashboard 에서):
    cd C:\\dashboard
    python purge_dryrun.py            (기본 데이터 경로 C:\\dashboard\\data)
    python purge_dryrun.py 종목폴더이름   (예: gold 만 계산)
"""
import os
import shutil
import sys
import tempfile

import bridge_signals as b

DATA_DIR = b.DATA_DIR
only = sys.argv[1].lower() if len(sys.argv) > 1 else None
HOURS = 24
DAYS = 7


def mb(n):
    return f"{n / 1e6:,.2f} MB"


def main():
    tmp = tempfile.mkdtemp(prefix="purge_dryrun_")
    total_before = total_after = 0
    try:
        sigs = [f for f in b.discover_signal_files() if only is None or f["instrument"].lower() == only]
        diags = [f for f in b.discover_diagnostic_files() if only is None or f["instrument"].lower() == only]
        floors = {}
        for i, f in enumerate(sigs):
            cp = os.path.join(tmp, f"sig_{i}.txt")
            shutil.copyfile(f["path"], cp)
            size0 = os.path.getsize(cp)
            b._set_pos(cp, size0)               # 브릿지가 이미 다 읽은 상태로 가정
            r = b.purge_file(cp, DAYS, True, HOURS)
            size1 = os.path.getsize(cp)
            total_before += size0
            total_after += size1
            print(f"[신호로그] {f['instrument']}/{os.path.basename(f['path'])}: {mb(size0)} -> {mb(size1)}  "
                  f"(줄 삭제 {r['removed']:,} / 하트비트 슬림화 {r.get('trimmed', 0):,} / 유지 {r['kept']:,})")
            fl = floors.setdefault(f["instrument"], {})
            for lbl, when in b.collect_unresolved_label_floor(cp).items():
                if lbl not in fl or when < fl[lbl]:
                    fl[lbl] = when
        from datetime import datetime, timedelta
        now = datetime.now(b._CT_ZONE).replace(tzinfo=None) if b._CT_ZONE else datetime.now()
        cutoff = (now - timedelta(hours=HOURS)).strftime("%Y%m%d %H:%M:%S")
        for i, f in enumerate(diags):
            cp = os.path.join(tmp, f"diag_{i}.txt")
            shutil.copyfile(f["path"], cp)
            size0 = os.path.getsize(cp)
            b._set_pos(cp, size0)
            r = b.purge_diag_file(cp, cutoff, floors.get(f["instrument"]))
            size1 = os.path.getsize(cp)
            total_before += size0
            total_after += size1
            print(f"[진단로그] {f['instrument']}/{os.path.basename(f['path'])}: {mb(size0)} -> {mb(size1)}  (줄 삭제 {r['removed']:,} / 유지 {r['kept']:,})")
        print()
        print(f"합계: {mb(total_before)} -> {mb(total_after)}  (줄어드는 양 {mb(total_before - total_after)})")
        print("※ 원본은 수정하지 않았습니다. 실제 삭제는 대시보드의 '신호달성 완전삭제' 버튼으로 하세요.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
