# -*- coding: utf-8 -*-
"""
log_size_report.py - 신호로그/진단로그가 어떤 줄로 용량을 차지하는지 보여주는 읽기 전용 점검 도구입니다(파일을 수정/삭제하지 않습니다).

사용법:  python log_size_report.py            (기본 경로 C:\\dashboard\\data)
         python log_size_report.py D:\\경로\\data

보여주는 것:
  1) 파일별 총 용량
  2) 신호로그: 줄 종류(HEARTBEAT, STATS_IMMEDIATE, 신호줄, 판정줄 등)별 줄 수/용량
  3) 신호로그: 나이별(24시간 이내 / 1~7일 / 7일 초과) 용량 - 삭제 버튼 기준과 같은 구분
  4) 진단로그: [DIAG] 태그별 용량 + 나이별 용량
이 표를 보면 "삭제 버튼이 어느 줄을 지울 수 있는지 / 용량을 크게 차지하는 줄이 무엇인지"를 바로 알 수 있습니다.
"""
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else r"C:\dashboard\data"
SIGNAL_RE = re.compile(r"^(?:[A-Za-z0-9]+_)?yesspot_signals_(.+)\.txt$")
DIAG_RE = re.compile(r"^.*diagnostic_log.*\.txt$", re.IGNORECASE)
TS_RE = re.compile(r"^(\d{8}) (\d{2}:\d{2}:\d{2})$")
TAG_RE = re.compile(r"\[DIAG\]\[([A-Z0-9_]+)\]")

try:
    from zoneinfo import ZoneInfo
    NOW = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)  # 로그 시각은 시카고(서버시간) 기준
except Exception:
    NOW = datetime.now()
    print("[주의] 시카고 시간대를 못 불러와(tzinfo 없음: pip install tzdata) PC 로컬시간 기준으로 나이를 계산합니다.\n")


def bucket(dt):
    if dt is None:
        return "시각없음"
    age = NOW - dt
    if age <= timedelta(hours=24):
        return "24시간 이내"
    if age <= timedelta(days=7):
        return "1~7일"
    return "7일 초과"


def mb(n):
    return f"{n / 1e6:,.2f} MB"


def parse_dt(date_s, time_s):
    try:
        return datetime.strptime(date_s + " " + time_s, "%Y%m%d %H:%M:%S")
    except Exception:
        return None


def show(title, rows):
    print(title)
    width = max([len(r[0]) for r in rows] + [8])
    for name, cnt, size in rows:
        print(f"  {name:<{width}}  {cnt:>9,}줄  {mb(size):>12}")
    print()


def main():
    if not os.path.isdir(DATA_DIR):
        print("데이터 폴더를 찾을 수 없습니다:", DATA_DIR)
        return
    grand = 0
    for inst in sorted(os.listdir(DATA_DIR)):
        d = os.path.join(DATA_DIR, inst)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            path = os.path.join(d, fname)
            is_sig = SIGNAL_RE.match(fname)
            is_diag = DIAG_RE.match(fname)
            if not (is_sig or is_diag):
                continue
            size = os.path.getsize(path)
            grand += size
            print("=" * 78)
            print(f"{inst}/{fname}   총 {mb(size)}")
            by_kind = defaultdict(lambda: [0, 0])
            by_age = defaultdict(lambda: [0, 0])
            by_tag = defaultdict(lambda: [0, 0])
            with open(path, "rb") as f:
                for raw in f:
                    n = len(raw)
                    line = raw.decode("utf-8", errors="ignore").rstrip("\r\n")
                    if not line.strip():
                        continue
                    if is_sig:
                        p = line.split(",")
                        kind = p[2] if len(p) >= 6 else "(형식이상)"
                        dt = parse_dt(p[3], p[4]) if len(p) >= 6 else None
                        by_kind[kind][0] += 1
                        by_kind[kind][1] += n
                        by_age[bucket(dt)][0] += 1
                        by_age[bucket(dt)][1] += n
                    else:
                        ts = line.split("\t", 1)[0].strip()
                        m = TS_RE.match(ts)
                        dt = parse_dt(m.group(1), m.group(2)) if m else None
                        by_age[bucket(dt)][0] += 1
                        by_age[bucket(dt)][1] += n
                        t = TAG_RE.search(line)
                        tag = t.group(1) if t else "(태그없음)"
                        by_tag[tag][0] += 1
                        by_tag[tag][1] += n
            if is_sig:
                show("[줄 종류별]", sorted(([k, v[0], v[1]] for k, v in by_kind.items()), key=lambda r: -r[2])[:12])
            else:
                show("[진단 태그별 상위 12개]", sorted(([k, v[0], v[1]] for k, v in by_tag.items()), key=lambda r: -r[2])[:12])
            order = ["24시간 이내", "1~7일", "7일 초과", "시각없음"]
            show("[나이별]", [[k, by_age[k][0], by_age[k][1]] for k in order if k in by_age])
    print("=" * 78)
    print("전체 합계:", mb(grand))
    print("※ 삭제 버튼 기준: 신호달성 완전삭제 = 확정된 신호 24시간 초과 + 진단로그 24시간 초과, 하트비트/통계/삭제로그 줄 = 7일 초과.")


if __name__ == "__main__":
    main()
