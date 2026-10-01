# -*- coding: utf-8 -*-
"""
================================================================================
[프로젝트 개요 - 새 대화창에서 이 파일을 처음 보는 경우를 위한 전체 설명]

이 파일의 역할:
  예스스팟(LS증권 예스트레이더의 JS 전략 스크립트)이 Main.PrintOnFile로
  기록하는 yesspot_signals.txt 파일을 0.3초 간격으로 감시하다가,
  새로 추가된 줄이 생기면 즉시 웹소켓으로 대시보드에 전달하는 "중계" 프로그램.

전체 시스템 구조:
  [예스스팟 전략 스크립트들 - signal_<종목>_min.js 등]
    -> Main.PrintOnFile로 신호 발견시마다 텍스트 줄로 기록
    -> [yesspot_signals.txt]  <- 이 파일을 이 bridge_signals.py가 감시
       -> [이 파일: bridge_signals.py] 가 WebSocket(ws://localhost:9100)으로 전달
          -> [dashboard_server.py] 가 서빙하는
             [yesspot_signals_dashboard.html] 웹페이지에서 실시간 목록으로 표시

신호 파일 형식 (한 줄에 하나, 콤마 구분):
  종목명,타임프레임라벨,신호종류,날짜(YYYYMMDD),시각(HH:MM:SS,시카고현지),가격
  예: 나스닥100,나스닥100 45분봉,BULL2,20260707,21:00:01,29518.00

[알아낸 함정들 - 다시 겪지 않도록 기록]
  1. 처음엔 파일을 계속 열어둔 채로(f.readline() 반복) 감시했더니,
     예스스팟의 Main.PrintOnFile 쓰기와 충돌해서 "파일을 열 수 없습니다"
     오류가 예스스팟 쪽에서 발생함. -> 매번 열었다 바로 닫는 방식
     (getsize로 변화 감지 후 필요할 때만 open)으로 바꿔서 해결.
  2. 대시보드를 새로고침하면 그동안 쌓인 신호를 다시 못 받아서 중복
     제거가 깨지는 문제 -> 새 대시보드가 연결될 때마다 파일 전체 내용을
     처음부터 한 번 다 보내주도록 handler()에서 처리함 (그 이후로는
     tail_loop이 새로 추가되는 줄만 계속 전달).
  3. Main.PrintOnFile 쪽에서, 신호 여러 개를 묶어서 한 번에 쓸 때
     끝에 개행을 안 붙이면 다음 기록과 한 줄로 합쳐져서 파싱이 깨짐
     (예스스팟 파일들에 반영된 이슈, 이 파일과는 무관하지만 같이 기록).
  4. [2026-08-31 발견] os.path.getsize()로 찍어둔 크기까지를 무조건
     "다 읽은 것"으로 치고 tail_loop의 읽기 위치를 전진시켰는데, 예스스팟이
     아주 긴 줄(특히 수십~수백 개 감시신호의 전체 이력이 다 들어가는
     HEARTBEAT_TICK/HEARTBEAT_MIN)을 쓰는 도중에 이 read()가 끼어들면
     그 줄이 개행문자 없이 중간에서 잘린 채로 읽힐 수 있었음 - 이 미완성
     줄까지 완전한 한 줄로 착각해서 파싱하면, 목록 뒤쪽에 있던 특정 신호의
     pk가 그 한 사이클만 통째로 누락된 것처럼 보임(예스스팟 스크립트 쪽엔
     REMOVAL_LOG/UNEXPLAINED_REMOVAL_ALERT가 전혀 없는데 대시보드에선 신호가
     한두 하트비트만 "사라짐"으로 보이는 실제사례로 확인). tail_loop을
     "마지막 개행문자까지만 완전한 내용으로 인정하고, 그 뒤 미완성 조각은
     다음 0.3초 주기로 미루는" 표준 안전 tail 패턴으로 수정.
  5. [2026-09-29 발견] purge_file()이 파일을 "읽고 -> 정리해서 -> 통째로
     다시 쓰는" 구조라, 그 읽기와 다시쓰기 사이(특히 파일이 커서 처리
     시간이 길어질 때)에 예스스팟이 새 줄을 추가로 쓰면 그 줄이 흔적도
     없이 사라지는 레이스컨디션이 있었음 - 덮어쓰기 바로 직전에 파일을
     한 번 더 확인해서 늘어난 부분을 이어붙이는 안전망으로 창을 대폭
     좁힘(완전 차단은 아니고, "처리 전체 시간" 창을 "파일 재확인 한 번"
     창으로 축소).

  6. [2026-09-29 수정] (a)알람창 프레임밀림 정규식이 스크립트 v5.13의 새 구분자("_")를 못 읽던 것 수정(";"와 "_" 둘 다 허용).
     (b)완전삭제가 (종목,타임프레임,날짜,시각)만으로 "판정 끝남"을 판단해서 같은 시각의 다른 신호(가격/종류 다름)까지
     지우던 것 수정(가격+신호종류까지 매칭). (c)STATS_IMMEDIATE가 같은 파일의 일반 신호줄과 이중집계되던 것 수정.

  7. [2026-09-30 추가] GATE_COUNT_SYNC(스크립트 v5.16/v5.17: v5.17부터 직전 동기화 이후 구간 기준): 워밍업이 게이트 카운터를 차트 기준으로 맞출 때 실시간 값과 2 이상 다르면
     남기는 진단줄. 원인 판별용 수치를 한글 문구로 조립해 대시보드 알림창에 저품질이관처럼 한 줄로 보낸다(데스크탑 알림창엔 안 띄움).

[대시보드 종료 버튼과의 연동]
  대시보드에서 "대시보드 종료" 버튼을 누르면, 이 프로그램에게
  websocket으로 {"cmd":"shutdown"} 메시지가 옵니다. 이걸 받으면:
    1) stop.flag 파일을 만들고
    2) 스스로 종료합니다(os._exit)
  dashboard_server.py는 이 stop.flag 파일이 생기는 걸 감시하고 있다가
  똑같이 자동으로 종료합니다. (두 프로그램이 동시에 깔끔하게 꺼짐)

[완전삭제(purge) 기능]
  대시보드의 "완전삭제" 버튼을 누르면, {"cmd":"purge", "days":7} 메시지가
  옵니다. 이걸 받으면 신호 파일 전체를 다시 읽어서:
    - 이미 달성(STATUS_ACHIEVED)/무효(STATUS_INVALID) 판정이 난 신호와
      그 판정 기록 줄
    - 신호 발생일이 오늘로부터 days일(기본 7일)보다 오래된 것
    이 둘 중 하나라도 해당하면 파일에서 완전히 지우고, 나머지만 남겨서
    파일을 다시 씁니다. (HEARTBEAT 줄은 신호가 아니라서 항상 보존)
  처리 결과({"cmd":"purge_result", "removed":N, "kept":M})를 요청한
  대시보드에게 돌려줍니다.
  [주의] 파일을 다시 쓰고 나면 tail_loop의 읽은 위치(last_pos)도 새
  파일 크기에 맞춰 갱신해줘야, 남은 줄들이 "새로 추가된 것"으로
  착각되어 다시 전부 방송되는 걸 방지할 수 있습니다.

[데스크톱 알람창 (MT5 스타일)]
  브라우저 알림(웹 Notification API)은 다른 프로그램(예스트레이더 등)이
  화면을 덮고 있으면 브라우저 자체가 뒤로 밀려서 안 보이는 근본적인
  한계가 있습니다. 이를 해결하기 위해, 이 브릿지 프로그램이 직접
  "항상 위에 뜨는" 진짜 윈도우 창(tkinter)을 새로 만듭니다.
    - 새 신호(BULL/BEAR)가 감지될 때마다, 이 창이 맨 위로 떠오르고
      최신 메시지 + 지금까지의 알림 이력(표)을 같이 보여줍니다.
    - "닫기"를 눌러도 창 자체는 완전히 안 없어지고 숨겨지기만 하며,
      이력(표)은 계속 남아있다가 다음 알림이 올 때 다시 나타납니다.
    - tkinter는 asyncio(브릿지의 메인 이벤트루프)와 같은 스레드에서
      돌릴 수 없어서(서로 블로킹), 별도 스레드에서 tkinter의 자체
      mainloop을 돌리고, 새 신호는 스레드 안전한 큐(queue.Queue)를
      통해 그 스레드로 전달합니다.
    - ENABLE_DESKTOP_ALERT = False 로 바꾸면 이 기능을 끌 수 있습니다.
  [주의] 이 기능은 실제 화면(디스플레이)이 있는 윈도우 PC에서만 정상
  동작합니다. tkinter가 설치 안 되어 있으면(파이썬 기본 포함이라
  거의 항상 있지만) 자동으로 이 기능만 건너뛰고 나머지는 그대로 동작합니다.

[함께 필요한 파일들 - 전부 같은 폴더에 있어야 함]
  yesspot_signals.txt (자동 생성됨, 아래 SIGNAL_FILE 경로)
  dashboard_server.py            - 대시보드 html을 8080 포트로 서빙
  yesspot_signals_dashboard.html - 실시간 신호 목록 웹페이지 (포트 9100으로 이 브릿지에 접속)
  start_yesspot_dashboard.bat    - 이 파일 + dashboard_server.py를 한번에 실행

[주의] 아래 SIGNAL_FILE 경로가, 예스스팟 6개 전략 파일들의 OUTPUT_FILE
변수와 정확히 같은 경로를 가리켜야 합니다.

[사용 방법] python bridge_signals.py  (계속 켜둔 채로 사용, Ctrl+C로 종료 가능)
================================================================================
"""

import asyncio
import json
import os
import re
import sys
import threading
import queue
import websockets
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
    _CT_ZONE = ZoneInfo("America/Chicago")
    _KST_ZONE = ZoneInfo("Asia/Seoul")
except Exception:
    _CT_ZONE = None
    _KST_ZONE = None

def ct_to_kst(date_str, time_str):
    """
    예스스팟이 기록하는 날짜(YYYYMMDD)/시각(HH:MM:SS, 시카고 현지)을
    한국시간 문자열("YYYY-MM-DD HH:MM:SS")로 정확히 변환합니다.
    (서머타임까지 자동으로 반영됨 - zoneinfo가 처리)
    실패하면 원본 그대로 돌려줍니다 (알림 자체가 안 뜨는 것보단 나음).
    """
    if not _CT_ZONE or not date_str or not time_str:
        return f"{date_str} {time_str}"
    try:
        dt_naive = datetime.strptime(date_str + time_str, "%Y%m%d%H:%M:%S")
        dt_ct = dt_naive.replace(tzinfo=_CT_ZONE)
        dt_kst = dt_ct.astimezone(_KST_ZONE)
        return dt_kst.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return f"{date_str} {time_str}"

# [2026-07-27 추가][추적유실 실제 근거 기록] 지금 이 순간을 한국시간
# 문자열로 반환합니다. 완전삭제가 아직 미확정인 신호를 강제로 지울 때,
# "정확히 언제 지워졌는지"를 실제 시각으로 기록해두기 위해 씁니다.
def now_kst_str():
    try:
        if _KST_ZONE:
            return datetime.now(_KST_ZONE).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "(KST 변환 실패, 서버 로컬시각)"

# ---------- 데스크톱 알람창 설정 ----------
ENABLE_DESKTOP_ALERT = True  # False로 바꾸면 알람창 기능을 완전히 끌 수 있음
alert_queue = queue.Queue()  # tail_loop(비동기) -> tkinter(별도 스레드)로 신호를 전달하는 통로

# [알람창 중복 억제] 가격이 오래 정체된 구간에서는, 서로 다른 여러
# 타임프레임이 우연히 똑같은 가격(SB값)을 동시에 잡아내면서 사실상
# 같은 정보가 알림으로 여러 번 우수수 뜨는 문제가 있었습니다. 그래서
# "같은 종목 + 같은 가격"이면, ALERT_DEDUP_WINDOW_SEC 안에는 신호세기/
# 방향(BULL1/BEAR2 등)이나 타임프레임이 달라도 한 번만 알림을 띄웁니다.
# (대시보드 자체에는 전부 그대로 다 표시되고, 이건 "알람창"에만 적용됨)
ALERT_DEDUP_WINDOW_SEC = 180  # 3분
_recent_alert_keys = {}  # (item, price) -> 마지막으로 알림 띄운 시각(time.time())

def should_alert(item_name, price):
    import time as _time
    key = (item_name, price)
    now = _time.time()
    last = _recent_alert_keys.get(key)
    if last is not None and (now - last) < ALERT_DEDUP_WINDOW_SEC:
        return False
    _recent_alert_keys[key] = now
    return True

# [완전 동일 신호 중복 방지] 예스스팟이 재시작되면서 워밍업 중 예전에
# 이미 기록됐던 신호와 "종목+타임프레임+신호종류+날짜+시각+가격" 6개
# 값이 전부 똑같은 줄을 시간이 한참 지난 뒤(3분보다 훨씬 뒤) 파일에
# 다시 쓰는 경우가 있습니다. 이러면 위의 should_alert()는 3분 윈도우가
# 이미 지나버려서 걸러내지 못하고, 알람창에 완전히 똑같은 신호가 또
# 뜹니다. 그래서 "완전히 동일한 신호"는 이 프로그램이 켜져 있는 동안
# 딱 한 번만 알림을 띄우도록 별도로 영구 기록해둡니다.
# (should_alert의 3분 룰은 "다른 신호인데 가격이 우연히 같은 경우"를
# 위한 것이라 그대로 유지하고, 이건 그와 별개로 추가되는 필터입니다.)
_seen_exact_signals = set()  # (item, label, kind, date, time, price)
# [근본수정][2026-09-26][메모리 누수] add만 하고 절대 지우지 않는 구조라
# 브릿지를 며칠씩 켜두면(재시작 없이) 이 집합이 무한정 자라는 게 확인됨
# (대시보드 쪽 별개 누수와는 다른, 이 파이썬 프로세스 자체의 메모리 증가
# 원인). 매번 검사하지 않고 개수가 상한을 넘을 때만, 신호 자체 날짜가
# 오래된(SEEN_SIGNALS_MAX_AGE_DAYS 이전) 항목만 골라 지운다 - "완전히
# 동일한 신호는 켜있는 동안 한 번만 알림"이라는 원래 목적상 최근 항목만
# 지켜지면 충분하다.
SEEN_SIGNALS_PRUNE_THRESHOLD = 50000
SEEN_SIGNALS_MAX_AGE_DAYS = 7

def _prune_seen_exact_signals():
    if len(_seen_exact_signals) <= SEEN_SIGNALS_PRUNE_THRESHOLD:
        return
    cutoff = (datetime.now() - timedelta(days=SEEN_SIGNALS_MAX_AGE_DAYS)).strftime("%Y%m%d")
    stale = set(k for k in _seen_exact_signals if len(k[3]) == 8 and k[3] < cutoff)
    _seen_exact_signals.difference_update(stale)

def is_duplicate_signal(parsed):
    key = (parsed["item"], parsed["label"], parsed["kind"],
           parsed["date"], parsed["time"], parsed["price"])
    if key in _seen_exact_signals:
        return True
    _seen_exact_signals.add(key)
    if len(_seen_exact_signals) % 1000 == 0:
        _prune_seen_exact_signals()
    return False

# [워밍업 중 발견된 과거 신호 필터링] 예스스팟이 재시작될 때, 큰 틱봉
# 주기(예: 900틱)는 워밍업으로 "최근 500봉"을 다시 훑는데, 이게 몇 달
# 전까지 거슬러 올라갈 수 있습니다. 이때 발견되는 신호는 "지금(파일에
# 새로 쓰여지는 시점)" 기준으로는 새 줄이라 알람 대상이 되지만, 신호
# 자체의 날짜는 예전 것일 수 있어서 헷갈립니다. 그래서 신호 자체의
# 날짜가 최근(기본 2일 이내)이 아니면 알람창에는 안 띄웁니다.
# (대시보드 목록 자체에는 그대로 다 표시됨 - 이건 알람창 전용 필터)
ALERT_MAX_AGE_DAYS = 2

def is_recent_signal(date_str):
    if not date_str or len(date_str) != 8:
        return True  # 형식이 이상하면 일단 걸러내지 않고 통과시킴 (안전한 기본값)
    try:
        sig_date = datetime.strptime(date_str, "%Y%m%d")
        # 시카고 현지 "오늘" 기준으로 비교 (신호 날짜 자체가 시카고 기준이므로)
        today_ct = datetime.now(_CT_ZONE).replace(tzinfo=None) if _CT_ZONE else datetime.now()
        age_days = (today_ct - sig_date).days
        return age_days <= ALERT_MAX_AGE_DAYS
    except Exception:
        return True

try:
    import winsound
    def play_alert_sound():
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
except ImportError:
    # 윈도우가 아닌 환경(예: 이 코드를 검토/테스트하는 개발 환경)에서는
    # winsound가 없어서 조용히 넘어갑니다 - 실제 배포 환경(윈도우)에서는 항상 있음
    def play_alert_sound():
        pass

SIGNAL_FILE = r"C:\dashboard\yesspot_signals.txt"  # [2026-07-19 이후] 새 로그는 아래 DATA_DIR 구조로 기록되지만, 이 경로에 남아있는 예전 기록(마이그레이션 전 과거 이력)이 있으면 참고용으로 그대로 둡니다 - 더 이상 새로 쓰이진 않습니다.
WS_PORT = 9100
STOP_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stop.flag")

# ============================================================
# [2026-07-19 신규][로그파일 분리] 예전엔 모든 종목/월물이 SIGNAL_FILE
# 하나에 다 같이 기록됐는데, 이제는 signal_*.js 쪽에서 종목×월물별로
# 로그 파일을 아예 나눠서 씁니다:
#   C:\dashboard\data\<종목폴더>\yesspot_signals_<월물>.txt
#   (data/ 아래 폴더명이 곧 instrument - 특정 종목명을 코드에 하드코딩하지 않음)
# 이 브릿지도 그에 맞춰 "파일 하나"가 아니라 "data/ 아래 발견되는
# 모든 로그 파일"을 동시에 감시하도록 바뀌었습니다. 새 종목/월물이
# 생기면(=generate_signal_files.py가 새 폴더/파일을 만들면) 재시작 없이
# 자동으로 같이 감시 대상에 들어옵니다(아래 discover_signal_files가
# tail_loop 매 주기마다 다시 스캔하기 때문).
# ============================================================
DATA_DIR = r"C:\dashboard\data"
# [2026-07-19 신규][대시보드 상단 월물/D-day 표시용]
# contracts.json은 "차기월물생성" 도구(contract_manager_server.py 등)가
# 저장하는 파일입니다 - 이 브릿지는 대시보드 헤더에 월물/D-day를
# 보여주기 위해 이 파일을 "읽기만" 합니다.
CONTRACTS_PATH = r"C:\dashboard\차기월물생성\contracts.json"
_FILE_NAME_RE = re.compile(r"^(?:[A-Za-z0-9]+_)?yesspot_signals_(.+)\.txt$")
# [2026-07-23 수정] 신호검색 JS 쪽에서 신호파일명 앞에 종목명을 붙이기로
# 바뀌어(예: <종목>_yesspot_signals_<월물>.txt)
# 정규식을 그에 맞게 확장함. "종목명_" 접두사는 선택사항(없어도 매칭)으로
# 만들어서, 아직 안 바뀐 예전 파일명(yesspot_signals_U26.txt)도 계속
# 인식되도록 하위호환을 유지함. 어느 쪽이든 월물(contract)은 그룹 1로
# 그대로 뽑히므로 뒤쪽 로직(instrument는 폴더명에서, contract는 이
# 정규식에서)은 안 건드려도 됨.

def discover_signal_files():
    """DATA_DIR 아래의 모든 종목×월물 로그 파일을 찾아서
    [{"path":절대경로, "instrument":"<data/ 아래 폴더명>", "contract":"<월물>"}, ...] 로 반환.
    파일이 실제로 존재하는지까지 확인(아직 예스스팟이 한 번도 안 써서
    파일 자체가 생성 안 된 경우는 자연스럽게 목록에서 빠짐 - 에러 아님)."""
    results = []
    if not os.path.isdir(DATA_DIR):
        return results
    try:
        instruments = sorted(os.listdir(DATA_DIR))
    except Exception:
        return results
    for instrument in instruments:
        inst_dir = os.path.join(DATA_DIR, instrument)
        if not os.path.isdir(inst_dir):
            continue
        try:
            filenames = sorted(os.listdir(inst_dir))
        except Exception:
            continue
        for fname in filenames:
            m = _FILE_NAME_RE.match(fname)
            if not m:
                continue
            results.append({
                "path": os.path.join(inst_dir, fname),
                "instrument": instrument,
                "contract": m.group(1),
            })
    return results

def file_key(instrument, contract):
    return instrument + "|" + contract

# [2026-07-27 추가][추적유실 원인 진단 - 진단로그 스트리밍] 신호검색 JS가
# 남기는 "<종목>_diagnostic_log_min_<월물>.txt" 같은 진단로그 파일들을 찾아서
# 대시보드로도 보내줍니다. 지금까지는 이 파일들이 서버 디스크에만 있고
# 대시보드로는 전혀 전달이 안 돼서, "그 시각에 무슨 일이 있었는지"를
# 대시보드에서 확인할 방법이 없었습니다. 신호 로그 파일과 정확히 같은
# 폴더(data/<종목>/)에, 파일명에 "diagnostic_log"가 들어간 .txt 파일을
# 전부 찾습니다(분봉/틱봉 파일명 규칙이 서로 달라도 다 잡히게 느슨한
# 패턴 사용).
_DIAG_FILE_NAME_RE = re.compile(r"^.*diagnostic_log.*\.txt$", re.IGNORECASE)

def discover_diagnostic_files():
    """DATA_DIR 아래의 모든 진단로그 파일을
    [{"path":절대경로, "instrument":"<data/ 아래 폴더명>", "filename":"..."}] 로 반환."""
    results = []
    if not os.path.isdir(DATA_DIR):
        return results
    try:
        instruments = sorted(os.listdir(DATA_DIR))
    except Exception:
        return results
    for instrument in instruments:
        inst_dir = os.path.join(DATA_DIR, instrument)
        if not os.path.isdir(inst_dir):
            continue
        try:
            filenames = sorted(os.listdir(inst_dir))
        except Exception:
            continue
        for fname in filenames:
            if not _DIAG_FILE_NAME_RE.match(fname):
                continue
            results.append({
                "path": os.path.join(inst_dir, fname),
                "instrument": instrument,
                "filename": fname,
            })
    return results

def load_contracts_config():
    """[2026-07-19 신규] contracts.json을 읽어서 대시보드에 그대로
    전달합니다. 파일이 없거나 형식이 깨졌으면 빈 instruments로 대체해서
    (대시보드 쪽이 예외 없이 "정보 없음"으로만 표시하게) 안전하게 처리합니다."""
    if not os.path.exists(CONTRACTS_PATH):
        return {"instruments": {}}
    try:
        with open(CONTRACTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {"instruments": data.get("instruments", {})}
    except Exception as e:
        print(f"  ? contracts.json 읽기 실패(무시): {e}")
        return {"instruments": {}}

connected_clients = set()

def write_stop_flag():
    try:
        with open(STOP_FLAG, "w", encoding="utf-8") as f:
            f.write("stop")
    except Exception:
        pass

async def handler(websocket):
    print("대시보드가 연결되었습니다.")
    connected_clients.add(websocket)
    # [신규][2026-09-29][월물정보 먼저 표시, 사용자 요청] 대시보드는 접속
    # 직후 곧바로 {"cmd":"get_contracts"}를 보내지만, 예전 구조상 이
    # handler()가 아래 이력 전송(및 진단로그 전송)을 전부 끝내고
    # "async for message in websocket:" 루프에 들어가야만 그 요청을
    # 처리할 수 있었다 - 즉 종목×월물 정보 응답이 구조적으로 항상
    # "신호 이력을 다 보낸 뒤"로 밀려날 수밖에 없었다(신호가 뜨는 데
    # 3~4초가 걸리는 동안 상단 월물/D-day 표시가 계속 비어있던 진짜
    # 원인). 대시보드가 요청하길 기다리지 않고, 연결 직후 이 브릿지가
    # 먼저 contracts_data를 보내버리면 이 구조적 지연 자체가 없어진다.
    # (대시보드가 onopen에서 보내는 get_contracts 요청은 그대로 남겨둠 -
    # 나중에 async for 루프에서 처리되면서 같은 데이터를 한 번 더
    # 보내게 되지만, handleContractsData가 그냥 덮어쓰기만 하므로 무해함)
    try:
        contracts = load_contracts_config()
        await websocket.send(json.dumps({"cmd": "contracts_data", **contracts}))
    except Exception as e:
        print("월물정보 선행 전송 중 오류:", e)
    # 새로 연결된 대시보드에게, 지금까지 모든 종목×월물 로그 파일에
    # 쌓인 전체 기록을 한 번에 보내줍니다 (파일이 여러 개로 나뉘어
    # 있어도, 대시보드 입장에서는 예전처럼 "전체 이력"으로 합쳐서 받음).
    try:
        # [수정][2026-09-29][접속 초기 속도개선, 사용자 요청 - 2번만] 예전엔
        # 이력 파일의 줄 하나마다 websocket.send()를 따로 호출했는데, 신호
        # 파일이 커진 만큼(같은 세션에서 확인한 100MB 사례) 그 줄 수만큼
        # 메시지 전송 오버헤드가 그대로 누적돼서 접속 직후 10초 가까이
        # 걸리게 된 진짜 원인이었다(대시보드 쪽 실측 지적). 각 줄의 실제
        # 파싱 결과(parsed)는 그대로 두고, 그것들을 BATCH_SIZE개씩 묶어서
        # {"cmd":"batch","items":[...]} 한 메시지로 보낸다 - 내용/순서는
        # 하나도 안 바뀌고 "몇 개씩 묶어서 보내는지"만 바뀐다(대시보드
        # 쪽도 processOneSignalMessage가 배치를 풀어서 기존과 완전히
        # 동일한 경로로 하나씩 처리하도록 맞춰뒀다).
        BATCH_SIZE = 300
        batch_buf = []
        for f in discover_signal_files():
            try:
                with open(f["path"], "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception as e:
                print(f"  ? [{f['instrument']}/{f['contract']}] 이력 읽기 실패(건너뜀): {e}")
                continue
            for line in content.splitlines():
                parsed = parse_line_with_source(line, f["instrument"], f["contract"])
                if parsed:
                    batch_buf.append(parsed)
                    if len(batch_buf) >= BATCH_SIZE:
                        await websocket.send(json.dumps({"cmd": "batch", "items": batch_buf}))
                        batch_buf = []
        if batch_buf:
            await websocket.send(json.dumps({"cmd": "batch", "items": batch_buf}))
            batch_buf = []
        # 과거 기록을 다 보냈다는 표시를 보냅니다.
        # (대시보드는 이 신호를 받은 뒤부터 도착하는 것만 "신규(N)"로 표시합니다)
        await websocket.send(json.dumps({"cmd": "history_end"}))

        # [2026-07-27 추가][추적유실 원인 진단 - 진단로그 스트리밍] 신호
        # 로그와 별개로 쌓이는 진단로그(타임아웃/재시도/콜드스타트 등
        # 스크립트 내부 사건 기록)도 파일별로 통째로 보내줍니다. 대시보드가
        # "이 신호가 사라진 시각 전후로 이 파일에 무슨 일이 있었는지"를
        # 직접 대조할 수 있게 하기 위함입니다(추측이 아니라 실제 로그 원문).
        for df in discover_diagnostic_files():
            try:
                with open(df["path"], "r", encoding="utf-8", errors="ignore") as fh:
                    diag_content = fh.read()
            except Exception as e:
                print(f"  ? [{df['instrument']}] 진단로그 읽기 실패(건너뜀): {e}")
                continue
            diag_lines = [ln for ln in diag_content.splitlines() if ln.strip()]
            if not diag_lines:
                continue
            await websocket.send(json.dumps({
                "cmd": "diagnostic_log",
                "instrument": df["instrument"],
                "filename": df["filename"],
                "lines": diag_lines,
            }))
    except Exception as e:
        print("초기 기록 전송 중 오류:", e)

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("cmd") == "shutdown":
                    print("대시보드에서 종료 요청을 받았습니다. 브릿지를 종료합니다...")
                    write_stop_flag()
                    asyncio.get_event_loop().call_later(0.5, lambda: os._exit(0))
                elif data.get("cmd") == "purge":
                    days = data.get("days", 7)
                    target = _parse_target(data)
                    print(f"대시보드에서 완전삭제 요청을 받았습니다. (기준: {days}일, 대상: {target or '전체'})")
                    result = purge_all(days, keep_pending=False, target=target)
                    await websocket.send(json.dumps({"cmd": "purge_result", **result}))
                    # [2026-07-27 추가][추적유실 실제 근거 기록] 이번 삭제로
                    # 아직 미확정이던 신호가 강제로 지워졌다면, 그 사실을
                    # 지금 연결된 모든 대시보드에게 즉시 알려서(브로드캐스트),
                    # 화면에 아직 그 행이 남아있다면 "왜 사라졌는지" 실제
                    # 삭제시각과 함께 바로 표시할 수 있게 합니다.
                    for evt in result.get("force_purged_pending", []):
                        await broadcast(json.dumps({"cmd": "pending_force_purged", **evt}))
                elif data.get("cmd") == "purge_keep_pending":
                    # [2026-07-19 신규] "신호달성 완전삭제" - 감시중 신호는
                    # 나이와 무관하게 제외하고, 이미 달성/무효로 끝난 것 중
                    # 오래된 것만 지웁니다.
                    days = data.get("days", 6)
                    target = _parse_target(data)
                    print(f"대시보드에서 '신호달성 완전삭제' 요청을 받았습니다. (기준: {days}일, 감시중 제외, 대상: {target or '전체'})")
                    result = purge_all(days, keep_pending=True, target=target)
                    await websocket.send(json.dumps({"cmd": "purge_keep_pending_result", **result}))
                elif data.get("cmd") == "get_report":
                    # [2026-07-19 신규] 보고서 페이지(yesspot_report.html)가
                    # 요청하는 종목×타임프레임별 집계 통계.
                    print("보고서 집계를 요청받았습니다.")
                    report = compute_report()
                    await websocket.send(json.dumps({"cmd": "report_data", **report}))
                elif data.get("cmd") == "get_contracts":
                    # [2026-07-19 신규] 대시보드 상단의 종목별 월물/D-day
                    # 표시용 - contracts.json 내용을 그대로 전달합니다.
                    contracts = load_contracts_config()
                    await websocket.send(json.dumps({"cmd": "contracts_data", **contracts}))
            except Exception as e:
                print("메시지 처리 중 오류:", e)
    finally:
        connected_clients.discard(websocket)
        print("대시보드 연결이 끊어졌습니다.")

async def broadcast(msg):
    if not connected_clients:
        return
    dead = set()
    for ws in list(connected_clients):
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)

def _parse_target(data):
    """WS 메시지에서 {"instrument":"<종목슬러그>","contract":"<월물>"} 같은 선택적
    대상 지정을 읽습니다. 없으면 None(=전체 파일 대상)을 돌려줍니다.
    [2026-07-19 신규] 프론트엔드가 아직 이 필드를 안 보내도(기존 동작
    그대로 "전체"로 동작) 문제없이 하위호환됩니다 - 나중에 대시보드에
    "이 월물만 삭제" 같은 선택 UI를 추가할 때 이 필드만 채워 보내면 됩니다."""
    instrument = data.get("instrument")
    contract = data.get("contract")
    if instrument and contract:
        return (instrument, contract)
    return None

# [신규][2026-09-30] GATE_COUNT_SYNC(게이트 카운터 불일치 진단) 알림창용 한글 문구 조립.
# 스크립트(Main.PrintOnFile)에 한글을 쓰면 인코딩이 깨질 수 있어, 스크립트는 영문 코드/숫자만 보내고
# 사람이 읽는 한글은 여기(파이썬)에서 만든다.
_GATE_SYNC_CAUSE_KR = {
    "TICK_SHORT": "수신틱 부족(실시간 시세가 차트보다 틱을 적게 받음)",
    "RESEED_LOSS": "워밍업 재시작으로 실시간 봉 손실",
    "LIVE_GAP_STOP": "무틱공백으로 실시간 정지",
    "LIVE_BAR_MISSED": "실시간이 봉을 놓침(원인 미상)",
    "COUNTER_LOW_OTHER": "구간 봉수는 맞는데 카운터가 작음(기타)",
    "WARM_OVERCOUNT": "워밍업이 봉을 과다 가산",
    "LIVE_OVERCOUNT": "실시간이 봉을 과다 계산",
}
def _gate_sync_kv(detail):
    kv = {}
    for seg in (detail or "").split("|"):
        if "=" in seg:
            k, v = seg.split("=", 1)
            kv[k.strip()] = v.strip()
    return kv
def _gate_sync_int(kv, key):
    try:
        return int(kv.get(key, "0"))
    except ValueError:
        return 0
_LIVE_SEED_WHY_KR = {
    "log_short": "틱 로그 부족(막 시작함)",
    "not_found": "실시간 틱이 차트와 안 맞음",
    "few_bars": "차트 봉 부족",
    "bucket_mismatch": "형성 중 봉이 현재 구간 아님",
    "no_calcBase": "계산기 복사 실패",
    "disabled": "이어받기 꺼짐",
    "fail": "원인 미상",
}
def compose_live_seed_reason(total, ok, fail, fail_items, pass_no):
    suffix = f" ({pass_no}번째 순환)" if pass_no else ""
    try:
        nfail = int(fail)
    except ValueError:
        nfail = 0
    if nfail <= 0:
        return f"{total}개 프레임 전부 이어받기 성공{suffix}"
    bits = []
    for it in fail_items:
        if ":" in it:
            lab, why = it.split(":", 1)
            bits.append(f"{lab}({_LIVE_SEED_WHY_KR.get(why, why)})")
        else:
            bits.append(it)
    return f"{total}개 중 성공 {ok} / 실패 {fail} - " + ", ".join(bits) + suffix
def compose_gate_sync_reason(sig_kind, live, chart, cause, detail):
    kv = _gate_sync_kv(detail)
    try:
        diff = int(chart) - int(live)
    except ValueError:
        diff = 0
    s = f"{sig_kind} 실시간 {live} / 차트 {chart} (차이 {diff:+d}) | 원인: {_GATE_SYNC_CAUSE_KR.get(cause, cause)}"
    # 스크립트 v5.17: 직전 동기화 이후 구간 기준 수치(liveD/chartD). 구버전 줄(live/chartLive/warm)도 그대로 표시되게 폴백.
    if "liveD" in kv or "chartD" in kv:
        bits = [f"직전 동기화 이후 구간: 실시간이 센 봉 {_gate_sync_int(kv, 'liveD')} / 차트에 생긴 봉 {_gate_sync_int(kv, 'chartD')}",
                f"재시작 {_gate_sync_int(kv, 'reseed')}회"]
    else:
        bits = [f"실시간봉 {_gate_sync_int(kv, 'live')}/같은구간 차트봉 {_gate_sync_int(kv, 'chartLive')}",
                f"워밍업가산 {_gate_sync_int(kv, 'warm')}", f"재시작 {_gate_sync_int(kv, 'reseed')}회"]
    if "ticks" in kv:
        bits.append(f"수신틱 {_gate_sync_int(kv, 'ticks'):,}(차트기준 {_gate_sync_int(kv, 'expTicks'):,}) 버린틱 {_gate_sync_int(kv, 'discard'):,}")
    if "gap" in kv:
        bits.append(f"무틱정지 {_gate_sync_int(kv, 'gap')}회")
    sigtxt = kv.get("sig")
    if sigtxt:
        bits.append("신호 " + sigtxt)
    return s + " | " + ", ".join(bits)

def parse_line(line):
    # 형식: 종목,타임프레임,신호,날짜,시각,가격[,7번째 필드]
    parts = line.strip().split(",")
    if len(parts) < 6:
        return None
    result = {
        "item": parts[0],
        "label": parts[1],
        "kind": parts[2],
        "date": parts[3],
        "time": parts[4],
        "price": parts[5],
    }
    # [7번째 필드 - kind에 따라 의미가 다름, 반드시 분리해서 처리]
    # - HEARTBEAT 줄: "지금 감시 중인 신호 키 목록"(pendingKeys)
    # - STATUS_ACHIEVED/STATUS_INVALID 줄: [2026-07-19 신규] 예스스팟
    #   쪽에서 새로 추가한 "서버시간(소요시간)" 필드, 예: "14:23:05(1H30M)".
    #   [2026-07-19 버그수정] 예전엔 이 구분 없이 무조건 pendingKeys로
    #   해석해버려서, 달성/무효 줄의 이 필드가 엉뚱하게 pendingKeys로
    #   잘못 채워지고 있었습니다. 이름이 겹치는 건 위험해서 바로잡음.
    #   이 필드는 report 집계(compute_report)에서 평균/최소/최대
    #   소요시간을 계산하는 데 씁니다.
    # [2026-08-04 추가][감시목록 제거 전수기록] REMOVAL_LOG: 예스스팟이
    # pendingSignals 배열에서 신호 하나가 실제로 빠지는 모든 지점(실시간
    # 판정/워밍업 재판정/철회/RESET재시작 초기화)에서 STATUS_* 판정라인과
    # 별개로 항상 즉시 남기는 감사용 백업 로그. STATUS_* 라인이 어떤
    # 이유로든 유실/미도달해도 이 줄만은 "언제 왜 사라졌는지"를 보장한다.
    # 형식: item,tf,REMOVAL_LOG,sdate,stime,price,reasonCode,pk,detail (9필드)
    if len(parts) >= 7:
        if result["kind"] == "HEARTBEAT":
            result["pendingKeys"] = parts[6]
        elif result["kind"] in _SIGNAL_KINDS:
            # [2026-08-18 수정][왼쪽평탄 3단계 별표] 신호검색 스크립트가
            # "삼각형 왼쪽으로 SB가 몇 봉까지 평평하게 이어졌는지"를 7번째
            # 필드로 실어보낸다: 0=해당없음, 0.5=5~9봉, 1=10봉이상.
            # 대시보드가 이 값을 그대로 별표 채움 비율(em)로 쓴다.
            result["starLevel"] = parts[6]
            # [제거][사용자 요청][철회기능 전체 제거] wasRestored(8번째 필드) 파싱 삭제됨
            # [근본수정][2026-09-10][9/10번째 필드 파싱 누락 발견] 신호검색
            # 스크립트는 v1.27(2026-09-07)부터 이미 9번째=꼭지점봉 서버시각
            # (apexDateTime), 10번째=꼭지점 높이(apexHeight)를 실어보내고
            # 있었고 대시보드도 sig.apexDateTime/sig.apexHeight를 읽는 코드가
            # 있었지만, 정작 이 파싱 함수에는 그 두 필드를 읽는 코드 자체가
            # 없었다 - 그래서 "가격시간" 칸이 항상 "-"만 표시되고 있었을
            # 것으로 추정됨(실제 운영 로그로 재확인 필요). 이번에 함께 수정.
            if len(parts) >= 9:
                result["apexDateTime"] = parts[8]
            if len(parts) >= 10:
                result["apexHeight"] = parts[9]
            # [신규][2026-09-10][목표삼각형 선행평탄구간/뾰족여부] 11번째=
            # 선행평탄구간(정수 봉수), 12번째=뾰족여부(1/0). 구버전 로그(이
            # 필드 없음)는 그냥 없는 채로 넘어가고, 대시보드가 "-"로 폴백.
            if len(parts) >= 11 and parts[10] != "":
                result["leftFlatRun"] = parts[10]
            if len(parts) >= 12 and parts[11] != "":
                result["apexSharp"] = (parts[11] == "1")
            # [신규][2026-09-18][예쁜삼각형/다이아몬드 배지] 13번째=1/0.
            # 구버전 로그(이 필드 없음)는 그냥 없는 채로 넘어가고, 대시보드가
            # 다이아몬드를 안 그림(false 취급).
            if len(parts) >= 13 and parts[12] != "":
                result["isPrettyTriangle"] = (parts[12] == "1")
        elif result["kind"] == "UNEXPLAINED_REMOVAL_ALERT":
            # [2026-08-26 신규][장시간 원인불명 소실 추적] parts[5]=재할당
            # 발생지점(site명), parts[6]=설명안된 pk 개수, parts[7]=pk목록
            # (최대10건, ;구분). T0170/M0005/M0066처럼 6개 알려진 경로
            # 어디에도 안 걸리는 소실이 재현될 때, 정확히 어느 코드
            # 지점에서 어떤 pk가 사라졌는지 즉시 특정하기 위한 알람.
            if len(parts) >= 8:
                result["reason"] = "지점=" + parts[5] + " 건수=" + parts[6] + " pk목록: " + parts[7]
        elif result["kind"] == "PENDING_MISMATCH_ALERT":
            # [2026-08-25 신규] 배열개수(parts[5])와 직렬화개수(parts[6])와
            # tf구분(parts[7])을 reason으로 조합해 대시보드에서 바로 확인.
            if len(parts) >= 8:
                result["reason"] = "배열개수=" + parts[5] + " 직렬화개수=" + parts[6] + " tf=" + parts[7]
        elif result["kind"] == "DEGRADED_DEFERRED":
            # [2026-09-25 신규][워밍업/재워밍업 저품질 이관 알림] 요청한
            # 타임프레임을 이번 순환 안에서 재시도(MAX_RETRY_ATTEMPTS)까지
            # 다 써도 못 받으면 신호검색 스크립트가 "저품질(degraded)"로
            # 표시하고 다음 순환으로 이관하는데, 예전엔 이 정보가 예스트레이더
            # 화면(MessageLog)에만 남고 대시보드로는 전혀 전달되지 않았다
            # (만들기로 했던 기능이 실제로는 안 만들어져 있었던 것을 뒤늦게
            # 확인). parts[5]=주기(cycle), parts[6]=소진된 재시도횟수.
            # [수정][2026-10-01][스크립트 v5.22] 순환 끝에 새로 저품질이 된 프레임을 한 줄에 모아 보낸다:
            # parts[5]=개수, parts[6]=소진된 재시도횟수, parts[7]=라벨1|라벨2|... (8번째 필드가 있으면 묶음 줄).
            # 예전 형식(프레임당 1줄, parts[5]=주기)도 그대로 읽는다.
            if len(parts) >= 8 and parts[7]:
                labels = [x for x in parts[7].split("|") if x]
                result["degradedBatch"] = True
                result["degradedCount"] = parts[5]
                result["degradedList"] = labels
                result["reason"] = parts[5] + "건 - " + ", ".join(labels) + " (재시도=" + parts[6] + "회 소진 - 다음 순환으로 이관)"
            elif len(parts) >= 7:
                result["reason"] = "주기=" + parts[5] + " 재시도=" + parts[6] + "회 소진 - 다음 순환으로 이관"
        elif result["kind"] == "LIVE_SEED_SUMMARY":
            # [신규][2026-10-01][스크립트 v5.24] 순환 끝에 한 줄로 오는 "실시간 이어받기" 결과. 형식:
            # item,첫라벨,LIVE_SEED_SUMMARY,date,time,총수,성공수,실패수,라벨:사유|라벨:사유...,순환번호
            if len(parts) >= 8:
                fail_items = [x for x in (parts[8] if len(parts) >= 9 else "").split("|") if x]
                result["seedTotal"] = parts[5]
                result["seedOk"] = parts[6]
                result["seedFail"] = parts[7]
                result["seedPass"] = parts[9] if len(parts) >= 10 else ""
                result["seedFailList"] = fail_items
                result["reason"] = compose_live_seed_reason(parts[5], parts[6], parts[7], fail_items, result["seedPass"])
        elif result["kind"] == "GATE_COUNT_SYNC":
            # [신규][2026-09-30] 형식: item,tf,GATE_COUNT_SYNC,date,time,신호종류,실시간카운터,차트카운터,원인코드,상세(key=value|...)
            if len(parts) >= 9:
                result["signalKind"] = parts[5]
                result["liveCount"] = parts[6]
                result["chartCount"] = parts[7]
                result["cause"] = parts[8]
                result["detail"] = parts[9] if len(parts) >= 10 else ""
                result["reason"] = compose_gate_sync_reason(parts[5], parts[6], parts[7], parts[8], result["detail"])
        elif result["kind"] == "WRITE_FAILURE_ALERT":
            # [2026-08-24 신규] 6번째 필드(parts[5])=버퍼적체줄수(대시보드가
            # price로 표시), 7번째 필드(parts[6])=실제 에러메시지(+선택적
            # 유실N줄 표기), 8번째 필드(parts[7])=밀린 줄들의 pk요약(라벨|
            # kind|날짜|시각|가격, 최대20건). 나중에 특정 신호가 "감시목록
            # 확인 안됨"으로 뜰 때 이 실패와 관련있는지 대조하는 용도.
            result["reason"] = parts[6]
            if len(parts) >= 8:
                result["reason"] = result["reason"] + " | 영향받은 신호: " + parts[7]
        elif result["kind"] == "REMOVAL_LOG":
            result["reasonCode"] = parts[6]
        elif result["kind"] == "BAR_DATA_UNSTABLE_ALERT":
            # [2026-09-14 신규][정확성 검증(방안1+3) 반복격리 경고] 같은 봉이
            # 다수결과 계속 어긋나 3회 이상 격리되면 뜬다. parts[5]=격리횟수,
            # parts[6]=타임프레임 라벨, parts[7]=이번에 받은 값(high|low),
            # parts[8]=합의값(high|low), parts[9]=이 봉이 아직 마감 안 된
            # "형성중" 상태인지(STILL_OPEN/ALREADY_CLOSED) - 추측이 아니라
            # 스크립트가 직접 계산해서 남긴 실측값.
            # [2026-09-16 수정][인코딩 문제 회피] 스크립트(Main.PrintOnFile)
            # 쪽에 한글을 쓰면 저장인코딩과 이 파이썬의 읽기인코딩(UTF-8)이
            # 어긋나는 환경에서 깨지는 게 실제로 확인돼서(사용자 스크린샷:
            # "STILL_OPEN(ㅆㄲ)"), parts[9]는 이제 순수 영문만 온다 - 사람이
            # 보기 좋은 한글 설명은 인코딩 문제가 없는 여기(파이썬)에서 붙인다.
            _status_label = {
                "STILL_OPEN": "형성중일가능성",
                "ALREADY_CLOSED": "마감시각지남(다른원인의심)",
            }
            if len(parts) >= 9:
                status_raw = parts[9] if len(parts) >= 10 else ""
                status_kr = _status_label.get(status_raw, status_raw)
                result["reason"] = ("라벨=" + parts[6] + " 격리횟수=" + parts[5] +
                                     " 수신값=" + parts[7] + " 합의값=" + parts[8] +
                                     (" 상태=" + status_kr if status_kr else ""))
        elif result["kind"] in ("STATUS_ACHIEVED", "STATUS_INVALID"):
            # [2026-07-23 추가] STATUS_RETRACTED: 정확도점검(신호검색 JS)이
            # authoritative 데이터로 재검증한 결과 "애초에 신호가 아니었음"이
            # 확인된 경우. 필드 구성(7번째=시각/8번째=사유)은 ACHIEVED/INVALID와
            # 완전히 동일한 포맷이라 파싱 로직을 그대로 공유합니다.
            result["achievedField"] = parts[6]
        elif result["kind"] == "GAP_CHECK":
            # [2026-08-03 추가][재시작 데이터갭 체크] 1안(OnBarAppended) 신호
            # 스크립트가 재시작 후 워밍업때, "죽기 직전 마지막 처리시각"과
            # "재시작 워밍업으로 받은 이력의 가장 오래된 시각"을 대조해서
            # 보내주는 줄. 7번째=체크된 라벨 개수, 8번째=라벨별 결과
            # (label^죽기전마지막^워밍업최초^갭초^완전커버여부(1/0), ";"로 구분).
            result["gapCount"] = parts[6]
        elif result["kind"] in ("SAVE_SCHEDULED", "SAVE_QUEUED", "SAVE_CONFIRMED"):  # [2026-08-26] SAVE_CONFIRMED는 하위호환용으로 남김
            # [2026-08-10 추가][저장추적 실제시각 근본수정] 예전엔 이 두 줄이
            # 4/5번째 필드(sdate,stime = 신호 자신의 봉시각, pk 매칭용 식별자)
            # 밖에 실제로 "이 단계가 언제 처리됐는지"를 담는 필드가 아예 없어서,
            # 대시보드가 저장예약/저장확인 시각을 어쩔 수 없이 신호등록시각과
            # 동일한 값(신호 봉시각)으로 표시하고 있었음(실제 처리시각과 무관하게
            # 항상 동일하게 보임 - 사용자 지적사항). 7번째 필드로 스크립트가
            # 실제 처리 시점에 계산한 서버시간("YYYYMMDD HH:MM:SS")을 새로
            # 추가했으므로 그대로 실어보낸다. 4/5번째 필드는 pk 매칭 용도로
            # 그대로 유지(의미를 바꾸지 않음).
            result["eventTime"] = parts[6]
            # [2026-09-01 신규][근본수정 - kind 필드 누락] 예전엔 이 줄에 진짜
            # 신호종류(BULL1 등)가 아예 없어서, 대시보드가 저장예약/확정 시각을
            # 조회할 때 쓸 저장키에 "SAVE_SCHEDULED"라는 이벤트타입 문자열밖에
            # 못 넣었다 - 조회 쪽은 진짜 kind(예: BEAR2)를 쓰니 저장/조회 키가
            # 영원히 안 맞아 항상 조회 실패하는 버그로 이어졌다(실제사례: T0430).
            # 8번째 필드로 스크립트가 실어보내는 진짜 kind를 그대로 전달한다.
            if len(parts) >= 8:
                result["signalKind"] = parts[7]
        elif result["kind"] == "STATS_IMMEDIATE":
            # [2026-08-17 추가][즉시판정 신호 로그 경량화] 예스스팟이 워밍업/
            # 재조회 중 "등록과 동시에 이미 달성/무효였던" 신호를 감시목록에
            # 올리지 않고 곧바로 통계 전용으로 압축해서 보내는 한 줄.
            # 형식: item,tf,STATS_IMMEDIATE,sdate,stime,price,ACHIEVED|INVALID,소요분,kind
            # 7번째=판정결과(ACHIEVED/INVALID).
            result["statsResult"] = parts[6]
        elif result["kind"] == "REGISTERED":
            # [2026-09-01 신규][등록경로 즉시기록] 예스스팟이 신호 등록
            # 순간(하트비트를 기다리지 않고 즉시) 남기는 줄. 7번째 필드가
            # 실시간(REAL)/재조회(WARM) 구분 태그 - 대시보드가 이 값을
            # 저장해뒀다가 모달의 "신호등록(...)" 문구에 [WARM]/[REAL]
            # 태그로 붙여 보여준다. 이 분기가 없으면 이 필드가 조용히
            # 버려져 대시보드가 등록경로를 영원히 못 보여주는 문제가 있었음
            # (실제 발견: T0160 - 원본 로그엔 WARM이 찍혀있는데 모달엔
            # 태그가 아예 안 보임).
            result["source"] = parts[6]
        elif result["kind"] == "PRETTY2_CONFIRMED":
            # [2026-09-26 신규][흰다이아몬드 배지 - 오른쪽 구름대 사후확인]
            # 기존 다이아몬드(◆, isPrettyTriangle)를 이미 통과한 신호에 대해
            # "꼭짓점 이후 N봉 동안 구름대가 유지되는지"를 나중에(즉시 판정
            # 불가 - 미래 데이터 필요) 재확인해서 보내는 줄. 이미 등록된
            # 신호에 배지만 추가/보류하는 후속 이벤트라 새 신호로 취급하면
            # 안 됨 - REGISTERED와 동일하게 신호테이블에 새 행을 만들지
            # 않고 대시보드가 pk로 기존 행을 찾아 배지만 붙인다.
            # 형식: item,tf,PRETTY2_CONFIRMED,sdate,stime,price,signalKind,confirmed(1/0),cases(예:"1|2", 파이프구분)
            if len(parts) >= 8:
                result["signalKind"] = parts[6]
                result["prettyTriangle2"] = (parts[7] == "1")
                # [2026-09-26 추가][케이스분리] 스크립트 v5.8부터 오른쪽
                # 구름대 판정이 3개의 독립된 케이스(두께평균/얇지만유지/짧은
                # 역전허용)로 나뉘어, 어느 케이스로 통과했는지가 9번째
                # 필드에 실려온다("1|2"처럼 파이프구분, 없으면 빈 문자열).
                # 구버전 로그(9번째 필드 자체가 없음)는 그냥 빈 문자열로
                # 폴백 - 대시보드가 케이스 정보 없이도 배지 자체는 그대로 뜬다.
                if len(parts) >= 9:
                    result["prettyTriangle2Cases"] = parts[8]
    # [2026-07-21 추가][판정사유] 8번째 필드
    # - STATUS_ACHIEVED/STATUS_INVALID 줄: 왜 그렇게 판정됐는지 신호검색
    #   스크립트가 직접 적어주는 실제 판정근거 문구.
    # - HEARTBEAT 줄: 지금 감시중인 신호들 각각의 실제 판정기준 원본값
    #   (상태/통과봉수/대기시간/눌림기록) - pendingKeys와 별개 필드로,
    #   매칭용(pendingKeys)과 표시용(pendingDetails)을 분리해서 기존
    #   ⏳/⚠️ 판정 로직은 그대로 두고 "사유" 칸 표시만 추가합니다.
    if len(parts) >= 8:
        if result["kind"] in ("STATUS_ACHIEVED", "STATUS_INVALID"):
            result["reason"] = parts[7]
        elif result["kind"] == "HEARTBEAT":
            result["pendingDetails"] = parts[7]
        elif result["kind"] == "GAP_CHECK":
            result["gapData"] = parts[7]
        elif result["kind"] == "REMOVAL_LOG":
            result["pk"] = parts[7]
        elif result["kind"] == "STATS_IMMEDIATE":
            result["statsDurationMin"] = parts[7]  # 8번째=소요분(빈 문자열일 수 있음)
    # [2026-08-04 추가][kind충돌 매칭버그 근본수정] REMOVAL_LOG의 9번째
    # 필드(자유서술 상세사유)와, STATUS_ACHIEVED/INVALID/RETRACTED의 9번째
    # 필드(원래 신호종류 BULL1/BULL2/BEAR1/BEAR2 - 판정라인엔 원래 이 정보가
    # 없어서, 같은 시각·같은 가격에 서로 다른 kind가 동시에 뜨면 대시보드가
    # 어느 행을 갱신해야 할지 구분 못 하는 구조적 문제가 있었음. 이제
    # 스크립트가 판정 시점의 원래 kind를 이 필드에 실어보내므로, 대시보드가
    # 정확히 그 kind의 행만 골라 갱신할 수 있음).
    if len(parts) >= 9:
        if result["kind"] == "REMOVAL_LOG":
            result["detail"] = parts[8]
        elif result["kind"] in ("STATUS_ACHIEVED", "STATUS_INVALID"):
            result["signalKind"] = parts[8]
        elif result["kind"] == "STATS_IMMEDIATE":
            result["signalKind"] = parts[8]  # 9번째=원래 신호종류(BULL1 등)
    return result

def parse_line_with_source(line, instrument, contract):
    """parse_line()에 "이 줄이 어느 종목·월물 로그 파일에서 왔는지"를
    덧붙입니다. 로그 파일 자체가 이미 종목×월물별로 나뉘어 있으므로,
    각 줄 안에 이 정보를 새로 넣을 필요 없이 "어느 파일에서 읽었는지"만
    알면 되는데, item/label 필드만으로는(예전처럼) 여러 월물이 섞여도
    구분이 안 되는 문제가 있었기 때문에 이렇게 파일 단위로 확실하게
    구분합니다."""
    parsed = parse_line(line)
    if parsed is None:
        return None
    parsed["instrument"] = instrument
    parsed["contract"] = contract
    return parsed

# tail_loop이 "각 파일마다 여기까지 읽었다"고 기억해두는 위치(바이트).
# [2026-07-19 변경] 예전엔 파일이 하나뿐이라 {"pos": N} 하나였는데, 이제는
# 파일마다 따로 추적해야 해서 절대경로 -> {"pos": N} 딕셔너리로 바꿨습니다.
# purge_file()에서도 이 값을 갱신해야 해서 모듈 전역에 둡니다.
last_pos_state = {}  # path -> {"pos": N}

def _get_pos(path):
    entry = last_pos_state.get(path)
    return entry["pos"] if entry else 0

def _set_pos(path, pos):
    last_pos_state[path] = {"pos": pos}

# ============================================================
# [2026-07-19 신규][통계 영구보관] 완전삭제로 원본 줄이 지워지면, 그
# 신호는 compute_report()가 다시는 셀 수 없게 됩니다 - "파일이 커져서
# 지웠더니 통계에서도 사라진다"는 문제입니다. 그래서 지우기 "직전"에,
# 지워질 줄들의 집계값(신호수/달성/무효/소요시간 합계·개수·최소·최대)만
# 종목×월물×타임프레임 단위로 별도 파일(.stats.json)에 누적해서 영구
# 보관합니다. 원본 줄(가격, 정확한 시각 등 상세 정보)은 사라지지만,
# "몇 개 중 몇 개가 달성됐는지", "평균 소요시간이 얼마인지" 같은 통계
# 숫자는 완전삭제를 몇 번을 해도 절대 줄어들지 않습니다.
def _archive_path(signal_path):
    base, _ext = os.path.splitext(signal_path)
    return base + ".stats.json"

def _load_archive(signal_path):
    path = _archive_path(signal_path)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_archive(signal_path, archive):
    path = _archive_path(signal_path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(archive, f, ensure_ascii=False)
    except Exception as e:
        print(f"  ? 통계 아카이브 저장 실패(무시 - 다음 삭제 때 다시 시도됨): {e}")

def _merge_into_archive(archive, tf_label, kind, duration_minutes):
    """archive는 {tf_label: {signals, achieved, invalid, durationSum,
    durationCount, durationMin, durationMax}} 구조. 호출한 쪽에서 저장은
    따로 해야 합니다(이 함수는 메모리 상의 dict만 갱신)."""
    entry = archive.setdefault(tf_label, {
        "signals": 0, "achieved": 0, "invalid": 0, "retracted": 0,
        "durationSum": 0.0, "durationCount": 0, "durationMin": None, "durationMax": None,
    })
    if kind in _SIGNAL_KINDS:
        entry["signals"] += 1
        return
    # [제거][사용자 요청][철회기능 전체 제거] STATUS_RETRACTED 트리거 삭제됨(스크립트가 더 이상 이 kind를 안 보냄)
    if kind not in ("STATUS_ACHIEVED", "STATUS_INVALID"):
        return
    entry["achieved" if kind == "STATUS_ACHIEVED" else "invalid"] += 1
    if duration_minutes is not None:
        entry["durationSum"] += duration_minutes
        entry["durationCount"] += 1
        entry["durationMin"] = duration_minutes if entry["durationMin"] is None else min(entry["durationMin"], duration_minutes)
        entry["durationMax"] = duration_minutes if entry["durationMax"] is None else max(entry["durationMax"], duration_minutes)


def _merge_stats_immediate_into_archive(archive, tf_label, stats_result, duration_minutes, dedup_key):
    """[2026-08-17 추가][즉시판정 신호 통계, 중복방지] STATS_IMMEDIATE는
    예스스팟의 seenKeys(SetUserValue 저장, 강제다운에 취약)가 유실되면
    같은 신호가 재워밍업 때 또 기록될 수 있음 - 그래서 파일에 여러 번
    나타나더라도 통계에는 "정확히 한 번"만 반영되도록, 아카이브 안에
    이미 반영한 신호의 고유키 목록(_statsImmediateSeenKeys)을 같이
    보관하고 매번 대조한다. tf_label별 집계와는 별개로 아카이브 전체에
    하나만 두는 전역 목록이다(고유키 자체에 tf/kind/시각/가격이 다
    들어있어 굳이 tf_label별로 나눌 필요가 없음)."""
    seen = archive.setdefault("_statsImmediateSeenKeys", [])
    if dedup_key in seen:
        return False  # 이미 이전에 통계에 반영됨 - 중복 카운트 방지
    seen.append(dedup_key)
    entry = archive.setdefault(tf_label, {
        "signals": 0, "achieved": 0, "invalid": 0, "retracted": 0,
        "durationSum": 0.0, "durationCount": 0, "durationMin": None, "durationMax": None,
    })
    entry["signals"] += 1
    if stats_result == "ACHIEVED":
        entry["achieved"] += 1
    elif stats_result == "INVALID":
        entry["invalid"] += 1
    if duration_minutes is not None:
        entry["durationSum"] += duration_minutes
        entry["durationCount"] += 1
        entry["durationMin"] = duration_minutes if entry["durationMin"] is None else min(entry["durationMin"], duration_minutes)
        entry["durationMax"] = duration_minutes if entry["durationMax"] is None else max(entry["durationMax"], duration_minutes)
    return True


def _evidence_log_path(signal_path):
    base_dir = os.path.dirname(signal_path)
    return os.path.join(base_dir, "purged_while_pending_evidence.log")

def log_forced_pending_purge(signal_path, item, label, kind, date, time_, price, reason):
    """[2026-07-27 추가][추적유실 실제 근거 기록] "완전삭제"(신호달성
    완전삭제가 아닌 일반 완전삭제) 버튼은 아직 달성/무효로 확정되지 않은
    (=감시 중인) 신호도 나이(기본 7일)가 넘으면 원본 파일에서 그냥
    지웁니다. 지금까지는 이게 아무 흔적도 안 남고 조용히 일어나서,
    나중에 "왜 이 신호가 감시목록에 없지?"를 절대 알 수 없었습니다.
    이제부터는 지워지는 바로 그 순간, 정확히 무엇이 왜 언제 지워졌는지
    사람이 읽을 수 있는 영구 로그 줄로 남깁니다 - 추측이 아니라 실제
    삭제 이벤트 그 자체를 기록하는 것입니다."""
    try:
        line = (
            f'[삭제시각(KST):{now_kst_str()}] item={item} label={label} kind={kind} '
            f'date={date} time={time_} price={price} '
            f'사유=FORCE_PURGED_WHILE_PENDING(아직 달성/무효로 확정되지 않은 상태였는데, '
            f'"완전삭제"(신호달성 완전삭제 아님) 버튼의 나이기준({reason}일)을 넘어서 '
            f'원본 파일에서 강제로 삭제됨 - 이후로는 이 신호에 대한 어떤 판정도 기록될 수 없음)'
        )
        with open(_evidence_log_path(signal_path), "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return {
            "item": item, "label": label, "kind": kind, "date": date, "time": time_, "price": price,
            "purgedAtKST": now_kst_str(),
        }
    except Exception as e:
        print(f"  ? [추적유실 증거기록] 실패(무시): {e}")
        return None

def purge_file(path, days, keep_pending):
    """[2026-07-19 재작성] 파일 하나를 대상으로 완전삭제를 수행합니다.
    이전에는 purge_signal_file()/purge_resolved_old_keep_pending() 두
    함수가 SIGNAL_FILE 하나를 각자 처리했는데, 이제는 파일이 여러 개라
    "파일 경로를 받아 그 파일 하나만 처리"하는 공용 함수로 합쳤습니다.

    keep_pending=False: 기존 "완전삭제"와 동일 - 달성/무효 판정이 난
        신호이거나, days일보다 오래된 신호면 무조건 지움.
    keep_pending=True: "신호달성 완전삭제"와 동일 - 아직 감시 중(=로그에
        확정 결과가 없음)인 신호는 나이와 무관하게 절대 안 지우고,
        "이미 달성/무효로 끝났으면서 오래된 것"만 지움.

    [레이스 컨디션 방지 - 기존 설계 그대로 유지] tail_loop이 아직 못
    읽은(방송 안 된) 뒷부분은 정리 대상에서 제외하고 그대로 보존합니다.
    """
    if not os.path.exists(path):
        return {"removed": 0, "kept": 0}

    with open(path, "rb") as f:
        raw = f.read()

    already_broadcast_pos = min(_get_pos(path), len(raw))
    already_bytes = raw[:already_broadcast_pos]
    pending_bytes = raw[already_broadcast_pos:]

    text = already_bytes.decode("utf-8", errors="ignore")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # [수정][2026-09-29][완전삭제 키충돌] 예전엔 (종목,타임프레임,날짜,시각)만으로 "판정 끝남"을 판단해서,
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

    # [2026-07-28 수정][타임존 불일치 버그수정] 신호의 date 필드는 서버시간
    # (시카고/CT) 기준인데, 여기서는 datetime.now()(브릿지가 도는 PC의
    # 로컬시간, 통상 KST)를 그대로 써서 cutoff를 계산하고 있었습니다.
    # KST와 CT는 14~15시간 차이가 나서, 자정 근처 신호는 완전삭제 기준일이
    # 최대 하루 가까이 어긋날 수 있었습니다. 191번째 줄(check_signal_age 등)
    # 에서 이미 쓰고 있는 _CT_ZONE과 동일한 방식으로 맞춥니다.
    now_ct = datetime.now(_CT_ZONE).replace(tzinfo=None) if _CT_ZONE else datetime.now()
    cutoff = (now_ct - timedelta(days=days)).strftime("%Y%m%d")
    archive = _load_archive(path)  # [2026-07-19 신규] 지워지기 전에 누적할 통계 아카이브
    archive_changed = False

    kept_lines = []
    removed_count = 0
    force_purged_pending = []  # [2026-07-27 추가] 이번 호출에서 "미확정인데 강제 삭제"된 신호 목록
    for ln in lines:
        p = ln.split(",")
        if len(p) < 6:
            kept_lines.append(ln)  # 형식이 이상한 줄은 건드리지 않고 보존
            continue

        item, label, kind, date, time_, price = p[0], p[1], p[2], p[3], p[4], p[5]

        if kind in ("HEARTBEAT", "REMOVAL_LOG", "GATE_COUNT_SYNC", "LIVE_SEED_SUMMARY"):
            # [2026-08-04 추가] REMOVAL_LOG는 실제 매매신호가 아니라 감사용
            # 백업 로그라서, HEARTBEAT와 동일하게 "나이"만으로 지운다.
            # resolved_keys(달성/무효/철회 매칭) 로직에 섞이면, RESET_WIPED
            # 처럼 대응되는 STATUS_* 줄이 영영 없는 경우 keep_pending=True에서
            # "영원히 미확정 pending"으로 오인돼 무한 보존되는 등 의미가
            # 왜곡될 수 있어 완전히 분리한다.
            if date < cutoff:
                removed_count += 1
            else:
                kept_lines.append(ln)
            continue

        if kind == "STATS_IMMEDIATE":
            # [2026-08-17 추가][즉시판정 신호 로그 경량화] 이 kind는
            # pendingSignals(감시목록)에 오른 적이 없는 신호라 resolved_keys
            # 매칭이 의미가 없다 - HEARTBEAT/REMOVAL_LOG처럼 나이로만 삭제
            # 여부를 판단한다. 단, REMOVAL_LOG와 달리 이건 실제 매매신호
            # 통계 수치라서, 지우기 전에 반드시 아카이브에 반영해야 한다
            # (그래야 완전삭제를 여러 번 해도 통계가 안 줄어듦). 중복
            # 방지(_merge_stats_immediate_into_archive의 고유키 대조)도
            # 함께 적용된다.
            if date < cutoff:
                removed_count += 1
                stats_result = p[6] if len(p) >= 7 else None
                duration = None
                if len(p) >= 8 and p[7]:
                    try:
                        duration = float(p[7])
                    except ValueError:
                        duration = None
                signal_kind = p[8] if len(p) >= 9 else ""
                dedup_key = f"{label}|{signal_kind}|{date}|{time_}|{price}"
                # [수정][2026-09-29] 같은 신호의 일반 줄이 이번에 같이 아카이브되면 그쪽에서 이미 집계되므로 건너뜀
                if dedup_key in stats_sig_keys:
                    pass
                elif _merge_stats_immediate_into_archive(archive, label, stats_result, duration, dedup_key):
                    archive_changed = True
            else:
                kept_lines.append(ln)
            continue

        if kind in ("STATUS_ACHIEVED", "STATUS_INVALID"):
            is_resolved = True
        elif kind in _SIGNAL_KINDS:
            is_resolved = ((item, label, date, time_, price, kind) in resolved_keys
                           or (item, label, date, time_, price) in resolved_nokind)
        else:
            is_resolved = (item, label, date, time_, price) in resolved_any_kind

        if keep_pending and not is_resolved:
            # [신호달성 완전삭제 전용] 감시중인 신호는 나이와 무관하게 보존
            kept_lines.append(ln)
            continue

        is_old = date < cutoff
        should_remove = is_old if keep_pending else (is_resolved or is_old)

        if should_remove:
            removed_count += 1
            # [2026-07-27 추가][추적유실 실제 근거 기록] "완전삭제"(일반,
            # keep_pending=False)가 아직 확정 안 된(=is_resolved가 False인)
            # 신호를 나이 때문에 지우는 바로 그 경우를, 지워지기 직전에
            # 증거로 영구 기록합니다. (신호달성 완전삭제로 지워지는 건
            # 이미 달성/무효로 확정된 것들이라 여기 해당 안 됨)
            if kind in _SIGNAL_KINDS and not is_resolved:
                evt = log_forced_pending_purge(path, item, label, kind, date, time_, price, days)
                if evt:
                    force_purged_pending.append(evt)
            # [2026-07-19 신규][통계 영구보관] 지워지는 줄이 신호발생/달성/
            # 무효 줄이면(하트비트는 위에서 이미 처리됨), 사라지기 직전에
            # 그 값을 아카이브에 더해둡니다 - compute_report()가 나중에
            # 이 아카이브를 읽어서 원본 줄 없이도 통계를 정확히 복원합니다.
            duration = None
            if kind in ("STATUS_ACHIEVED", "STATUS_INVALID") and len(p) >= 7:
                duration = parse_duration_minutes(p[6])
            _merge_into_archive(archive, label, kind, duration)
            archive_changed = True
            continue

        kept_lines.append(ln)

    if archive_changed:
        _save_archive(path, archive)

    new_already = ("\n".join(kept_lines) + "\n").encode("utf-8") if kept_lines else b""

    # [근본수정][2026-09-29][완전삭제 레이스컨디션 안전망] 위에서 raw를
    # 읽은 시점과 지금(파일을 통째로 덮어쓰기 직전) 사이에, 예스스팟
    # 실행파일이 이 파이썬과 전혀 무관한 별도 OS 프로세스로서 새 줄
    # (신호/하트비트)을 이 파일에 추가로 썼을 수 있다. 그 줄은 raw에
    # 안 들어있었으니 pending_bytes에도 없는데, 바로 아래에서 "wb"로
    # 파일 전체를 new_content로 덮어써버리면(추가모드가 아니라 전체
    # 교체라서) 그 사이에 추가된 줄이 흔적도 없이 통째로 사라진다 -
    # 100MB급 파일일수록(처리 시간이 길어질수록) 실제로 걸릴 확률이
    # 올라가는 진짜 레이스였음(추측이 아니라 raw/wb 코드 구조상 확정적).
    # 완전히 막으려면 두 프로세스가 파일락을 공유해야 하는데 그건
    # 예스스팟 스크립트 쪽까지 건드려야 하는 큰 변경이라, 대신 "덮어쓰기
    # 바로 직전에 한 번 더 실제 파일을 다시 읽어서, raw 길이 이후로
    # 늘어난 부분이 있으면 그대로 이어붙인다" - 창을 "처리에 걸리는 시간
    # 전체"에서 "파일 열고 읽고 닫는 시간 한 번"으로 줄여서(수백~수천배
    # 좁아짐) 사실상 안전망 역할을 하게 한다. 이 늘어난 부분도 pending_bytes와
    # 마찬가지로 파싱하지 않고 원문 그대로 보존하므로(다음 tail_loop
    # 주기가 정상적으로 읽어서 방송), 줄 중간이 아직 개행 없이 잘려있어도
    # 안전하다(기존 tail_loop의 "마지막 개행까지만 완전한 내용" 로직이
    # 그대로 처리함).
    extra_bytes = b""
    try:
        with open(path, "rb") as f:
            f.seek(len(raw))
            extra_bytes = f.read()
    except Exception as e:
        print(f"  ? [완전삭제 안전망] 추가분 재확인 실패(무시): {e}")

    new_content = new_already + pending_bytes + extra_bytes

    with open(path, "wb") as f:
        f.write(new_content)

    _set_pos(path, len(new_already))
    return {"removed": removed_count, "kept": len(kept_lines), "force_purged_pending": force_purged_pending}


def purge_all(days, keep_pending, target=None):
    """[2026-07-19 신규] discover_signal_files()로 찾은 파일들 중 target에
    해당하는 것만(target이 None이면 전체) purge_file()로 정리하고,
    결과를 합산해서 돌려줍니다.
    target: (instrument, contract) 튜플 또는 None(전체 대상)."""
    files = discover_signal_files()
    if target is not None:
        files = [f for f in files if (f["instrument"], f["contract"]) == target]

    total_removed = 0
    total_kept = 0
    per_file = []
    all_force_purged_pending = []  # [2026-07-27 추가] 전체 파일 합산
    for f in files:
        result = purge_file(f["path"], days, keep_pending)
        total_removed += result["removed"]
        total_kept += result["kept"]
        for evt in result.get("force_purged_pending", []):
            evt["instrument"] = f["instrument"]
            evt["contract"] = f["contract"]
            all_force_purged_pending.append(evt)
        per_file.append({
            "instrument": f["instrument"], "contract": f["contract"],
            "removed": result["removed"], "kept": result["kept"],
        })

    label = "신호달성 완전삭제" if keep_pending else "완전삭제"
    print(f"[{label}] 완료 - 총 {total_removed}개 삭제, {total_kept}개 유지 "
          f"({len(files)}개 파일 대상: {[f['instrument']+'/'+f['contract'] for f in files]})")
    if all_force_purged_pending:
        print(f"  !! [추적유실 실제 근거 기록] 아직 미확정 상태였는데 나이 때문에 "
              f"강제 삭제된 신호 {len(all_force_purged_pending)}개 - purged_while_pending_evidence.log에 기록됨")
    return {"removed": total_removed, "kept": total_kept, "files": per_file,
            "force_purged_pending": all_force_purged_pending}


# ============================================================
# [2026-07-19 신규][보고서 집계]
# yesspot_report.html이 접속시 {"cmd":"get_report"}를 보내면, 이 함수가
# 신호 파일 전체를 다시 훑어서 종목×타임프레임(분/틱 주기)별로
#   - 신호발생/신호달성/신호무효 개수, 성공율
#   - 달성/무효까지 걸린 시간의 평균/최소/최대(분 단위)
# 를 집계해서 돌려줍니다. 이 값들은 예스스팟이 각 신호 줄 끝에 붙이는
# "서버시간(소요시간)" 필드(예: "14:23:05(1H30M)")에서 소요시간만
# 뽑아서 계산합니다 - 서버시간 자체(HH:MM:SS)는 이 집계에선 안 쓰고
# 소요시간(분)만 씁니다.
#
# [설계 이유 - 왜 매번 전체 파일을 다시 읽는지] 신호 파일은 완전삭제
# 버튼을 누르기 전까진 계속 쌓이기만 하고, 이 집계는 "보고서 페이지를
# 열거나 새로고침할 때"만 1회성으로 계산하면 되는 정도의 빈도라, 매번
# 전체를 다시 읽어도 실무적으로 충분히 빠릅니다(실시간 tail_loop처럼
# 매 0.3초 도는 게 아님). 파일이 너무 커져서 느려지면 완전삭제 버튼으로
# 정리하면 됩니다.
_DURATION_RE = re.compile(r"\((?:(\d+)H)?(\d+)M\)\s*$")

def parse_duration_minutes(achieved_field):
    """'14:23:05(1H30M)' 또는 '14:23:05(45M)' 형태에서 소요시간(분)만 추출."""
    if not achieved_field:
        return None
    m = _DURATION_RE.search(achieved_field)
    if not m:
        return None
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    return hours * 60 + minutes

def parse_timeframe_label(label):
    """'T0030' -> (True, 30) / 'M0005' -> (False, 5) / 그 외 -> None."""
    if not label or len(label) < 2:
        return None
    kind_char = label[0]
    try:
        num = int(label[1:])
    except ValueError:
        return None
    if kind_char == "T":
        return (True, num)
    if kind_char == "M":
        return (False, num)
    return None

_SIGNAL_KINDS = ("BULL1", "BULL2", "BEAR1", "BEAR2")

def compute_report():
    """[2026-07-19 재작성] SIGNAL_FILE 하나 대신, discover_signal_files()로
    찾은 모든 종목×월물 로그 파일을 순회하며 집계합니다. 집계 키에
    contract(월물)를 추가해서, 같은 종목의 서로 다른 월물(예: 나스닥
    U26과 Z26)이 통계에서 섞이지 않고 따로 집계되도록 했습니다.

    [2026-07-19 추가][완전삭제 후에도 통계 보존] 지금 파일에 남아있는
    줄만 세면, 완전삭제로 지워진 만큼 통계가 줄어듭니다("파일이 커져서
    지웠더니 통계도 사라진다" 문제). 그래서 각 파일의 "지금 남아있는
    내용"과, 그 파일이 완전삭제될 때마다 미리 저장해둔 "아카이브
    (.stats.json)"를 합산해서 보여줍니다 - 원본 줄이 지워져도 통계
    숫자는 절대 안 줄어듭니다."""
    contracts_cfg = load_contracts_config().get("instruments", {})

    stats = {}   # (item, contract, isTick, period) -> {signals, achieved, invalid, durationSum, durationCount, durationMin, durationMax}
    items_set = set()

    def get_bucket(item, contract, is_tick, period):
        key = (item, contract, is_tick, period)
        return stats.setdefault(key, {
            "signals": 0, "achieved": 0, "invalid": 0, "retracted": 0,
            "durationSum": 0.0, "durationCount": 0, "durationMin": None, "durationMax": None,
        })

    def add_duration(bucket, d):
        if d is None:
            return
        bucket["durationSum"] += d
        bucket["durationCount"] += 1
        bucket["durationMin"] = d if bucket["durationMin"] is None else min(bucket["durationMin"], d)
        bucket["durationMax"] = d if bucket["durationMax"] is None else max(bucket["durationMax"], d)

    for f in discover_signal_files():
        instrument, contract, path = f["instrument"], f["contract"], f["path"]

        # 이 파일의 item(종목)명을 최대한 확실하게 알아냅니다: 1순위
        # contracts.json 설정값, 2순위 로그 안의 실제 item 필드(설정이
        # 없거나 오래된 경우 대비), 그마저도 없으면 폴더 슬러그로 대체.
        item_name = None
        inst_cfg = contracts_cfg.get(instrument)
        if inst_cfg:
            item_name = inst_cfg.get("nameEnDefault")

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            content = ""

        # [2026-08-17 추가][STATS_IMMEDIATE 중복방지] 아카이브를 라이브 스캔
        # 전에 미리 읽어서, "이미 예전에 완전삭제되면서 아카이브에 반영된
        # 키"가 혹시 크래시로 인한 재기록으로 파일에 다시 나타나도 또
        # 세지 않도록 대조 목록으로 씀. 아래에서 이 파일 자체를 archive_*로
        # 새로 갱신하진 않는다(집계 전용 - 저장은 purge_file()에서만 함).
        archive = _load_archive(path)
        # [수정][2026-09-29][통계 이중집계 방지] 이 파일에 일반 신호줄이 이미 있는 신호는 STATS_IMMEDIATE로
        # (스크립트 재시작 후 재검출) 또 세지 않는다.
        signal_keys_live = set()
        for _ln in content.splitlines():
            _p = _ln.strip().split(",")
            if len(_p) >= 6 and _p[2] in _SIGNAL_KINDS:
                signal_keys_live.add(f"{_p[1]}|{_p[2]}|{_p[3]}|{_p[4]}|{_p[5]}")
        archived_stats_immediate_keys = set(archive.get("_statsImmediateSeenKeys", []))
        seen_stats_immediate_keys_live = set()  # 이번 파일 라이브 스캔 안에서의 중복도 같이 방지

        for line in content.splitlines():
            parts = line.strip().split(",")
            if len(parts) < 6:
                continue
            item, label, kind = parts[0], parts[1], parts[2]
            if item_name is None:
                item_name = item  # 설정에 없으면 로그에 실제 찍힌 이름으로 대체
            if kind == "HEARTBEAT":
                continue
            tf = parse_timeframe_label(label)
            if tf is None:
                continue
            is_tick, period = tf
            items_set.add(item_name)
            bucket = get_bucket(item_name, contract, is_tick, period)

            if kind in _SIGNAL_KINDS:
                bucket["signals"] += 1
            elif kind == "STATUS_ACHIEVED":
                bucket["achieved"] += 1
                if len(parts) >= 7:
                    add_duration(bucket, parse_duration_minutes(parts[6]))
            elif kind == "STATUS_INVALID":
                bucket["invalid"] += 1
                if len(parts) >= 7:
                    add_duration(bucket, parse_duration_minutes(parts[6]))
            # [제거][사용자 요청][철회기능 전체 제거] STATUS_RETRACTED 분기 삭제됨(스크립트가 더 이상 이 kind를 안 보냄)
            elif kind == "STATS_IMMEDIATE":
                # [2026-08-17 추가][즉시판정 신호, 중복방지 집계] 고유키
                # (tf|신호종류|날짜|시각|가격) 기준으로 이번 스캔 내 중복과
                # 과거 아카이브에 이미 반영된 것 둘 다 걸러내고 딱 한 번만
                # 센다 - seenKeys(예스스팟 쪽)가 크래시로 유실돼 같은 신호가
                # 파일에 여러 번 나타나도 통계 숫자는 항상 정확히 한 번만
                # 반영된다.
                stats_result = parts[6] if len(parts) >= 7 else None
                duration_min = None
                if len(parts) >= 8 and parts[7]:
                    try:
                        duration_min = float(parts[7])
                    except ValueError:
                        duration_min = None
                signal_kind = parts[8] if len(parts) >= 9 else ""
                dedup_key = f"{label}|{signal_kind}|{parts[3]}|{parts[4]}|{parts[5]}"
                if dedup_key in signal_keys_live or dedup_key in archived_stats_immediate_keys or dedup_key in seen_stats_immediate_keys_live:
                    continue
                seen_stats_immediate_keys_live.add(dedup_key)
                bucket["signals"] += 1
                if stats_result == "ACHIEVED":
                    bucket["achieved"] += 1
                    add_duration(bucket, duration_min)
                elif stats_result == "INVALID":
                    bucket["invalid"] += 1
                    add_duration(bucket, duration_min)

        # [2026-07-19 신규] 이 파일의 아카이브(과거 완전삭제로 지워졌던
        # 분량의 집계값)를 같은 버킷에 합산합니다.
        if item_name is None:
            item_name = instrument  # 로그도 비어있고 설정도 없으면 최후 수단
        for tf_label, a in archive.items():
            tf = parse_timeframe_label(tf_label)
            if tf is None:
                continue
            is_tick, period = tf
            items_set.add(item_name)
            bucket = get_bucket(item_name, contract, is_tick, period)
            bucket["signals"] += a.get("signals", 0)
            bucket["achieved"] += a.get("achieved", 0)
            bucket["invalid"] += a.get("invalid", 0)
            bucket["retracted"] += a.get("retracted", 0)
            bucket["durationSum"] += a.get("durationSum", 0.0)
            bucket["durationCount"] += a.get("durationCount", 0)
            if a.get("durationMin") is not None:
                bucket["durationMin"] = a["durationMin"] if bucket["durationMin"] is None else min(bucket["durationMin"], a["durationMin"])
            if a.get("durationMax") is not None:
                bucket["durationMax"] = a["durationMax"] if bucket["durationMax"] is None else max(bucket["durationMax"], a["durationMax"])

    rows = []
    for (item, contract, is_tick, period), s in stats.items():
        resolved = s["achieved"] + s["invalid"]
        rows.append({
            "item": item,
            "contract": contract,
            "isTick": is_tick,
            "period": period,
            "signals": s["signals"],
            "achieved": s["achieved"],
            "invalid": s["invalid"],
            "retracted": s.get("retracted", 0),
            "successRate": round(s["achieved"] / resolved * 100, 1) if resolved > 0 else None,
            "avgMin": (s["durationSum"] / s["durationCount"]) if s["durationCount"] > 0 else None,
            "minMin": s["durationMin"],
            "maxMin": s["durationMax"],
        })

    return {"rows": rows, "items": sorted(items_set)}

async def tail_loop():
    """[2026-07-19 재작성] SIGNAL_FILE 하나가 아니라, DATA_DIR 아래 발견되는
    모든 종목x월물 로그 파일을 동시에 감시합니다.

    [새 파일이 나중에 나타나는 경우] generate_signal_files.py가 새 월물용
    폴더/파일을 막 만들었거나, 그 월물의 예스스팟 스크립트가 이제 막 처음
    신호를 기록하기 시작해서 파일이 지금 이 순간 처음 생긴 경우 -
    이런 파일은 last_pos_state에 아직 없으므로, "처음 보는 파일"로
    판단해서 그 파일의 현재 내용 전체를 "새로 추가된 것"으로 취급해
    브로드캐스트합니다(_get_pos가 없으면 0을 돌려주는 동작을 그대로
    활용). 이미 켜져 있던 대시보드도 이 신호들을 실시간으로 받게 됩니다.
    """
    while not os.path.isdir(DATA_DIR):
        print(f"데이터 폴더를 아직 찾지 못했습니다. 대기 중... ({DATA_DIR})")
        await asyncio.sleep(1)

    print(f"{DATA_DIR} 아래 신호 로그 파일들을 감시합니다.")

    # [중요] _seen_exact_signals는 메모리에만 있어서, bridge_signals.py
    # 자체가 재시작되면 텅 비워집니다. 이 상태에서 예스스팟이 워밍업 중
    # "파일에 이미 있던 신호"와 완전히 똑같은 걸 다시 쓰면, bridge
    # 입장에선 "이번 실행에서 처음 보는 신호"라서 다시 알림을 띄우는
    # 문제가 있었습니다. 그래서 감시를 시작하기 전에, 지금 존재하는 모든
    # 로그 파일에 이미 쌓여있는 신호들을 미리 한 번 훑어서(알림은 안
    # 띄우고) _seen_exact_signals만 채워두고, 각 파일의 읽은 위치도
    # "지금까지의 크기"로 맞춰서 기존 내용은 새로 브로드캐스트하지
    # 않도록 합니다.
    initial_files = discover_signal_files()
    primed_total = 0
    for f in initial_files:
        try:
            with open(f["path"], "r", encoding="utf-8", errors="ignore") as fh:
                existing_content = fh.read()
            for line in existing_content.splitlines():
                parsed = parse_line(line)
                if parsed and parsed["kind"] not in ("HEARTBEAT", "STATUS_ACHIEVED", "STATUS_INVALID", "GAP_CHECK", "STATS_IMMEDIATE", "PRETTY2_CONFIRMED", "GATE_COUNT_SYNC", "LIVE_SEED_SUMMARY"):
                    is_duplicate_signal(parsed)
                    primed_total += 1
            _set_pos(f["path"], os.path.getsize(f["path"]))
        except Exception as e:
            print(f"  ? [{f['instrument']}/{f['contract']}] 기존 신호 미리 등록 중 오류(무시): {e}")
    print(f"기존 신호 {primed_total}개를 중복방지 목록에 미리 등록했습니다. (파일 {len(initial_files)}개)")

    # [신규][2026-09-10][진단로그 실시간 알림 - 시작시 위치 프라이밍]
    # 신호파일과 똑같은 이유 - 프라이밍 없이 바로 tail을 시작하면, 브릿지가
    # 재시작될 때마다 그동안 쌓여있던 진단로그 전체가 "방금 막 발생한 일"인
    # 것처럼 한꺼번에 알림으로 쏟아진다. 시작 시점에 각 진단로그 파일의
    # 현재 크기로 위치를 미리 맞춰서, 그 이후에 새로 추가되는 줄만 실시간
    # 알림 대상이 되게 한다(접속 시의 전체이력 전송은 handler()가 별도로
    # 담당 - 그건 그대로 유지).
    for df in discover_diagnostic_files():
        try:
            _set_pos(df["path"], os.path.getsize(df["path"]))
        except Exception:
            pass

    while True:
        try:
            for f in discover_signal_files():
                path = f["path"]
                instrument, contract = f["instrument"], f["contract"]
                try:
                    size = os.path.getsize(path)
                except FileNotFoundError:
                    continue  # 스캔과 읽기 사이에 파일이 없어질 수도 있음(드묾) - 다음 주기에 다시 시도

                prev_pos = _get_pos(path)
                if size > prev_pos:
                    # [근본수정][부분기록(partial write) 경쟁조건 방지] 예전엔
                    # os.path.getsize()로 미리 찍어둔 크기까지를 무조건 "다 읽은
                    # 것"으로 치고 위치를 그만큼 전진시켰다. 그런데 예스스팟이
                    # 아주 긴 줄(특히 수십~수백 개 감시신호의 전체 이력이 다
                    # 들어가는 HEARTBEAT_TICK/HEARTBEAT_MIN)을 쓰는 도중에 이
                    # read()가 끼어들면, 그 줄이 개행문자 없이 중간에서 잘린 채로
                    # 읽힐 수 있다. 이 경우 splitlines()가 그 미완성 줄까지
                    # "완전한 한 줄"로 착각해서 그대로 파싱해버리면, pendingKeys
                    # 뒷부분(예: 목록 뒤쪽에 있던 특정 신호의 pk)이 그 한 사이클만
                    # 통째로 누락된 것처럼 보인다 - 실제로는 신호검색 스크립트
                    # 쪽에서 한 번도 놓친 적이 없는데도(REMOVAL_LOG/UNEXPLAINED_
                    # REMOVAL_ALERT가 전혀 없는데 신호가 한두 하트비트만 "사라짐"
                    # 으로 보이는 실제사례로 확인) 대시보드에는 그렇게 보였던
                    # 원인. 이제 "마지막 개행문자까지"만 완전한 내용으로 인정하고,
                    # 그 뒤에 개행 없이 남은 조각(아직 쓰는 중일 수 있는 미완성
                    # 줄)은 이번엔 아예 처리하지 않고 그대로 남겨둔다 - 다음
                    # 0.3초 주기에 그 줄이 마저 다 써진 뒤 완전한 형태로 다시
                    # 읽히게 된다(표준 안전 tail 패턴: 완전한 줄만 소비).
                    # [바이너리로 위치 계산] 텍스트모드로 디코딩한 뒤 다시
                    # 인코딩해서 바이트오프셋을 역산하면 UTF-8 멀티바이트 문자나
                    # errors="ignore"로 버려진 바이트 때문에 오차가 생길 수 있어,
                    # 아예 바이트 그대로 다뤄서 개행 위치를 찾는다.
                    with open(path, "rb") as fh_b:
                        fh_b.seek(prev_pos)
                        new_bytes = fh_b.read()
                    last_newline_b = new_bytes.rfind(b"\n")
                    if last_newline_b == -1:
                        # 이번에 읽은 덩어리 전체에 개행이 하나도 없음 -> 전부
                        # 아직 쓰는 중인 미완성 줄일 수 있으므로 이번 주기엔
                        # 아무것도 처리하지 않고 위치도 전진시키지 않는다.
                        complete_bytes = b""
                    else:
                        complete_bytes = new_bytes[:last_newline_b + 1]  # 마지막 개행문자까지 포함
                        _set_pos(path, prev_pos + len(complete_bytes))
                    complete_data = complete_bytes.decode("utf-8", errors="ignore")
                    for line in complete_data.splitlines():
                        parsed = parse_line_with_source(line, instrument, contract)
                        if not parsed:
                            continue
                        print(f"신호 수신[{instrument}/{contract}]:", parsed)
                        await broadcast(json.dumps(parsed))

                        # [2026-08-04 수정][발견된 버그 수정] SAVE_SCHEDULED/
                        # SAVE_CONFIRMED가 이 제외목록에 원래 빠져있어서, 신호가
                        # "등록"만 돼도(실제 BULL/BEAR 매매신호가 아닌데도)
                        # 데스크탑 알림창에 진짜 신호처럼 팝업이 뜨고 있었음.
                        # REMOVAL_LOG(신규 감사로그)도 같은 이유로 실제 매매
                        # 신호가 아니므로 함께 제외한다.
                        # [2026-08-05 추가][같은 유형 버그 재발견] 오늘 새로
                        # 생긴 REGISTRATION_BASIS(등록판정근거)와
                        # PENDING_STATE_LOAD_FAILED(상태로드실패)도 똑같이
                        # 이 목록에서 빠져있었음 - 신호 하나 등록될 때마다
                        # REGISTRATION_BASIS가 "진짜 신호처럼" 알림창에 또
                        # 떠서 팝업이 중복/뒤섞여 보이던 문제(신고사례)의
                        # 원인. 앞으로 이런 진단전용 kind를 추가할 때마다
                        # 이 목록도 같이 챙겨야 함.
                        # [2026-08-17 추가] STATS_IMMEDIATE(즉시판정 신호의
                        # 통계전용 압축줄)도 실제 매매신호 팝업 대상이 아님 -
                        # 감시목록에 오른 적도 없던 신호라 알림을 띄우면 오히려
                        # 혼란만 준다.
                        # [2026-09-16 추가][같은 유형 버그 재발견 - 이번엔 이
                        # 목록을 관리하는 사람(나) 스스로가 빠뜨림] 정확성
                        # 검증(다수결/격리) 기능을 추가하며 만든
                        # BAR_DATA_UNSTABLE_ALERT도 실제 매매신호가 아닌
                        # 시스템 진단 이벤트인데, 이 목록에 추가를 깜빡해서
                        # 진짜 신호처럼 데스크탑 팝업에 뜨던 것이 사용자
                        # 스크린샷으로 확인됨. 이 목록의 존재 이유(위 주석들)
                        # 를 다시 한번 확인하고 추가.
                        # [2026-09-25 추가] DEGRADED_DEFERRED(저품질 이관 알림)도 실제
                        # 매매신호가 아닌 시스템 진단 이벤트 - 데스크탑 알람창(tkinter)
                        # 팝업은 안 띄우고 대시보드 모달로만 보낸다(아래 broadcast로 이미
                        # 감).
                        _NON_ALERT_KINDS = ("HEARTBEAT", "STATUS_ACHIEVED", "STATUS_INVALID",
                                            "GAP_CHECK", "SAVE_SCHEDULED", "SAVE_QUEUED", "SAVE_CONFIRMED", "REMOVAL_LOG",
                                            "REGISTRATION_BASIS", "PENDING_STATE_LOAD_FAILED", "STATS_IMMEDIATE",
                                            "STALL_ALERT", "STALL_RECOVERED", "WRITE_FAILURE_ALERT", "PENDING_MISMATCH_ALERT",
                                            "UNEXPLAINED_REMOVAL_ALERT", "EXCEL_RESTORE_FAILURE_ALERT", "REGISTERED",
                                            "SCRIPT_STARTED", "BAR_DATA_UNSTABLE_ALERT", "DEGRADED_DEFERRED",
                                            "PRETTY2_CONFIRMED", "GATE_COUNT_SYNC", "LIVE_SEED_SUMMARY")
                        if ENABLE_DESKTOP_ALERT and parsed["kind"] not in _NON_ALERT_KINDS:
                            if not is_duplicate_signal(parsed):
                                if is_recent_signal(parsed["date"]) and should_alert(parsed["item"], parsed["price"]):
                                    alert_queue.put(parsed)
                        elif ENABLE_DESKTOP_ALERT and parsed["kind"] in ("STATUS_ACHIEVED", "STATUS_INVALID"):
                            alert_queue.put(parsed)
                        elif ENABLE_DESKTOP_ALERT and parsed["kind"] == "HEARTBEAT":
                            alert_queue.put(parsed)
                        # [신규][2026-09-23][프레임밀림 표시 버그수정] REGISTERED는
                        # _NON_ALERT_KINDS에 있어서 첫 분기를 못 타고, 위 두
                        # elif에도 안 걸려서 alert_queue에 아예 안 들어가고
                        # 있었음 - 그래서 알람창 쪽에 저장해둔 source 조회
                        # 코드가 한 번도 실행될 기회가 없었다(진짜 원인).
                        # REGISTERED 자체는 알람창에 새 행을 만들진 않지만
                        # (알람창 쪽에서 continue 처리), 프레임밀림 정보를
                        # 저장하려면 큐까지는 도달해야 한다.
                        elif ENABLE_DESKTOP_ALERT and parsed["kind"] == "REGISTERED":
                            alert_queue.put(parsed)
                        # [신규][2026-09-29][missing 오판정 근본수정] SAVE_SCHEDULED도
                        # REGISTERED와 같은 이유(_NON_ALERT_KINDS에 있어 그냥 두면
                        # 큐에 아예 안 들어감)로 명시적으로 큐까지 보낸다 - 알람창
                        # 쪽에서 새 행을 만들진 않지만(continue 처리), 실제
                        # 등록시각(eventTime)을 real_reg_time_by_pk에 저장해야
                        # refresh_wait_missing_marks가 대시보드와 같은 기준으로
                        # 판정할 수 있다.
                        elif ENABLE_DESKTOP_ALERT and parsed["kind"] == "SAVE_SCHEDULED":
                            alert_queue.put(parsed)
                        # GAP_CHECK/SAVE_CONFIRMED/REMOVAL_LOG는 알림/팝업 대상이
                        # 아님 - 브라우저 대시보드에만 전달(위 broadcast로 이미
                        # 보냄), 데스크탑 알림창엔 안 넣음.
                elif size < prev_pos:
                    # 파일이 새로 만들어졌거나, purge_file()이 방금 파일을
                    # 정리해서 크기가 줄어든 경우 -> 그 함수가 이미
                    # last_pos_state를 올바르게 맞춰뒀으니 여기선 아무것도
                    # 안 하고 다음 루프에서 그 값 그대로 사용합니다.
                    pass
        except Exception as e:
            print("파일 읽기 오류(잠시 후 재시도):", e)

        # [신규][2026-09-10][진단로그 실시간 알림 - diag_alert] 기존엔
        # discover_diagnostic_files()가 접속 시 딱 한 번, 그때까지 쌓인
        # 진단로그 전체를 통째로만 보내줬다(위 handler() 참고) - 그래서
        # "지금 막 벌어진 일"을 실시간으로는 볼 수 없었다. 사용자가 요청한
        # 세 가지 정보(요청 타임아웃 / 유령응답으로 폐기 / 정상매칭 확인)를
        # 대시보드 알림창에 실시간으로 띄우기 위해, 진단로그 파일도 신호
        # 파일과 같은 방식(바이트 오프셋 추적, 마지막 개행까지만 소비)으로
        # tail하되 - 다른 진단태그(SLOW_RESPONSE 등)는 그대로 두고 이
        # 3개 태그만 걸러서 별도 cmd로 브로드캐스트한다.
        # [신규][2026-09-10][diag_alert 나스닥100만 필터링] MATCH_CONFIRMED
        # 로그는 나스닥100 분봉에만 넣었는데, REQUEST_TIMEOUT/GHOST_RESPONSE는
        # 원래 6개 파일 전부에 있던/이미 넣은 진단이라 SP500 등 다른
        # 종목에서도 diag_alert가 떴었다. 사용자 요청으로 우선 나스닥100만
        # 보이게 필터링한다 - 다른 종목도 보고 싶어지면 이 목록에 추가하면 됨.
        # [수정][2026-09-10][나스닥100 "분봉"만 필터링 - min/tick 구분 누락
        # 수정] 종목 폴더(nasdaq100)까지만 걸렀더니 같은 폴더에 있는 틱봉
        # 진단로그(파일명에 diagnostic_log_tick_이 들어감)도 같이 통과되고
        # 있었다(MATCH_CONFIRMED는 애초에 분봉에만 있어 안 걸렸지만,
        # REQUEST_TIMEOUT/GHOST_RESPONSE는 틱봉에도 있어서 같이 떴음).
        # 파일명에 "diagnostic_log_min_"이 들어가는 것만 통과시킨다.
        # [수정][2026-09-11][전체 종목으로 확장] 사용자 요청: 나스닥100만
        # 필터링해뒀던 게 오히려 SP500/GOLD도 같이 나와야 하는데 막고
        # 있었음(MATCH_CONFIRMED가 나스닥에만 있어서 이 필터 자체가 처음
        # 생겼던 건데, BAR_MISMATCH/SUSPECT_LABEL_DUP 등 다른 태그까지
        # 여기 걸려서 의도치 않게 다른 종목을 막아버렸다) - 종목 필터를
        # 완전히 제거하고 전체 종목 대상으로 바꾼다.
        # [수정][2026-09-11][대책없는 알림 제거] 사용자 요청: REQUEST_TIMEOUT/
        # GHOST_RESPONSE/MATCH_CONFIRMED는 떠도 딱히 대응하는 게 없어서
        # (전체 페이싱만 뭉뚱그려 늦추는 정도) 알림만 산만하게 만들었음 -
        # 대시보드 실시간 전달 대상에서 제거(스크립트가 진단로그 파일에
        # 남기는 건 그대로 유지 - 나중에 필요하면 참고 가능). 향후
        # "최근 N회 순환 중 실패비율을 추적해 페이싱을 비례해서 조정"
        # 같은 실질적 대책이 마련되면 그때 다시 붙일 것.
        # SUSPECT_LABEL_DUP(라벨오귀속 의심)/BAR_MISMATCH(차트정확도)는
        # 각각 목적이 분명해서 그대로 유지.
        # [수정][2026-09-13][대책없는 표시 추가 제거] BAR_MISMATCH(차트정확도)도
        # 마찬가지로 실시간으로 띄워봐야 자동으로 하는 조치가 없어서 사용자
        # 요청으로 제거 - 알림창은 물론 "차트정확도" 디버깅창에도 이제
        # 아무것도 안 뜬다(liveBarMismatchGroups가 더 이상 채워지지 않음).
        # SUSPECT_LABEL_DUP(라벨오귀속 의심)만 남김 - 이건 등록 자체를
        # 막을지 말지 판단할 실질적 근거로 쓰이는 것이라 성격이 다름.
        # [수정][2026-09-13][대책없는 표시 전부 제거] REQUEST_TIMEOUT/
        # GHOST_RESPONSE/MATCH_CONFIRMED/BAR_MISMATCH와 같은 이유로
        # SUSPECT_LABEL_DUP도 제거 - 발견해도 등록을 막거나 병합하는 등의
        # 실제 조치가 전혀 없이 로그만 남기던 것이라 똑같이 대책없는
        # 표시였음(사용자 지적). 스크립트가 진단로그 파일에 남기는 건
        # 그대로 유지 - 나중에 필요하면 참고 가능. 실제 대책(예: 안정성
        # 확인 후에만 등록하는 것)이 마련되면 그게 진짜 조치가 된다.
        _DIAG_ALERT_TAGS = ()
        try:
            for df in discover_diagnostic_files():
                dpath = df["path"]
                try:
                    dsize = os.path.getsize(dpath)
                except FileNotFoundError:
                    continue
                dprev_pos = _get_pos(dpath)
                if dsize > dprev_pos:
                    with open(dpath, "rb") as fh_b:
                        fh_b.seek(dprev_pos)
                        new_bytes = fh_b.read()
                    last_nl = new_bytes.rfind(b"\n")
                    if last_nl == -1:
                        continue  # 아직 쓰는 중인 미완성 줄 - 다음 주기에 재시도
                    complete_bytes = new_bytes[:last_nl + 1]
                    _set_pos(dpath, dprev_pos + len(complete_bytes))
                    for dline in complete_bytes.decode("utf-8", errors="ignore").splitlines():
                        for tag in _DIAG_ALERT_TAGS:
                            if tag in dline:
                                # [근본수정][2026-09-10][diag_alert 한글깨짐 재발 방지]
                                # 이 진단로그 파일도 신호파일과 똑같이 예스트레이더
                                # (Windows/JScript)가 직접 쓴 텍스트라, 그 안의 한글
                                # ("[객체:N]", "정상매칭", "냉각" 등)은 대시보드까지
                                # 오는 동안 깨질 수 있다(이전에 이미 확인된 것과 동일
                                # 원인). raw 줄을 그대로 보내는 대신, label=XXX처럼
                                # 순수 영문/숫자인 부분만 정규식으로 뽑아서 별도
                                # 필드로 보낸다 - 대시보드가 표시 문구는 자기 쪽
                                # (안전한 UTF-8) 한글로 직접 조립하고, 이 label 필드는
                                # 참고용으로만 붙인다.
                                m = re.search(r"label=(\S+)", dline)
                                label = m.group(1) if m else None
                                if label is None and tag == "[DIAG][SUSPECT_LABEL_DUP]":
                                    # [임시진단][2026-09-10] 이 태그는 label=XXX가 아니라
                                    # label_new=XXX(...) 형태라 위 정규식이 못 잡는다 -
                                    # 대시보드 한줄요약용으로 label_new만 따로 추출.
                                    m2 = re.search(r"label_new=(\S+?)\(", dline)
                                    label = m2.group(1) if m2 else None
                                payload = {
                                    "cmd": "diag_alert",
                                    "instrument": df["instrument"],
                                    "filename": df["filename"],
                                    "tag": tag.strip("[]").replace("DIAG][", ""),
                                    "label": label,
                                }
                                # [임시진단][2026-09-10][라벨오귀속 원인규명용 - 원인
                                # 찾으면 이 if블록 제거] SUSPECT_LABEL_DUP 줄은
                                # label_existing=.../label_new=...로 label=XXX 형태가
                                # 아니라서 위 정규식이 못 잡는다 - 그런데 이 줄은
                                # 순수 영문/숫자/기호뿐이라(한글 없음) 통째로 보내도
                                # 인코딩 깨짐 위험이 없다(한글 멀티바이트 문자만
                                # 깨지는 문제였음, ASCII는 안전).
                                if tag in ("[DIAG][SUSPECT_LABEL_DUP]", "[DIAG][BAR_MISMATCH]"):
                                    # [근본수정][2026-09-10/11][detail 한글깨짐] dline 전체를
                                    # 그대로 보내면 앞에 붙는 "타임스탬프\t[객체:N]\t" 부분의
                                    # "객체"(한글)가 깨진다(실제 화면에서 "[ü:0]"로 확인) -
                                    # 태그가 시작하는 지점부터만 잘라서 순수 영문/숫자
                                    # 메시지만 보낸다. 둘 다 한글이 없는 태그라 안전.
                                    payload["detail"] = dline[dline.index(tag):]
                                await broadcast(json.dumps(payload))
                                break
                elif dsize < dprev_pos:
                    _set_pos(dpath, 0)  # 파일이 새로 만들어졌거나 정리됨 - 처음부터 다시
        except Exception as e:
            print("진단로그 tail 오류(잠시 후 재시도):", e)

        await asyncio.sleep(0.3)

def start_alert_window():
    """
    "항상 위에 뜨는" 진짜 윈도우 알람창을 만듭니다 (MT5 스타일).
    이 함수는 별도 스레드에서 실행되어야 합니다 - tkinter의 mainloop()이
    그 스레드를 계속 점유하기 때문에, asyncio 이벤트루프(브릿지의 메인
    작업)와 절대 같은 스레드에서 돌리면 안 됩니다.

    새 신호는 alert_queue(스레드 안전한 큐)를 통해 여기로 전달받습니다.
    tail_loop()이 있는 asyncio 스레드에서 alert_queue.put(...)을 하면,
    이 함수 안의 poll_queue()가 200ms마다 큐를 확인해서 창을 갱신합니다.

    [구조] 한국시간(KST) / 종목 / 타임프레임 / 신호 / 가격 5개 열로 표시.
    (예전엔 "시각+메세지" 2열이었는데, 시각도 브릿지가 처리한 시각이
    아니라 신호 자체의 정확한 한국시간으로, 나머지도 각각 구분되는
    열로 보여달라는 요청으로 재구성함)
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        print("[알람창] tkinter를 사용할 수 없어 데스크톱 알람창 기능을 건너뜁니다.")
        return

    root = tk.Tk()
    root.title("알람")
    root.geometry("560x300")
    root.attributes("-topmost", True)
    root.withdraw()  # 처음엔 숨겨둠 - 첫 알림이 올 때 자동으로 나타남

    # ---------- [2026-07-17 추가][필터 기능] ----------
    # 대시보드와 마찬가지로, 알람창에도 방향(Bull/Bear)·종목별 필터를
    # 추가합니다. 체크를 끄면 그 시점 이후로 들어오는 신호는 이 알람창의
    # 표/팝업/소리에서 걸러집니다(대시보드 화면 자체에는 그대로 다
    # 표시됨 - 필터는 이 알람창에만 적용). [주의] 실시간 알림 로그라는
    # 성격상, 이미 표에 추가된 과거 행까지 소급해서 숨기지는 않습니다 -
    # 필터를 켠/끈 시점부터 앞으로 들어오는 신호에만 적용됩니다.
    filter_frame = tk.Frame(root)
    filter_frame.pack(fill="x", padx=6, pady=(6, 0))

    tk.Label(filter_frame, text="필터:", fg="#888888").pack(side="left", padx=(0, 6))

    # [2026-07-17 추가][창 제목에 필터 상태 표시] 체크박스를 하나라도 끄면,
    # 작업표시줄/타이틀바에 보이는 창 제목 자체에 "지금 뭘 걸러내고
    # 있는지"가 바로 보이게 합니다. 창이 최소화돼 있어도 작업표시줄에
    # 마우스를 올리면 제목이 보이므로, 굳이 창을 열지 않아도 지금
    # 필터가 걸려있는지 한눈에 알 수 있습니다. 전부 체크(기본 상태)면
    # 원래 제목("알람") 그대로 둡니다.
    def update_title():
        off_dirs = [d for d in ("BULL", "BEAR") if not dir_vars[d].get()]
        off_items = [it for it, v in item_vars.items() if not v.get()]
        if not off_dirs and not off_items:
            root.title("알람")
            return
        excluded_parts = []
        if off_dirs:
            excluded_parts.append("/".join(off_dirs))
        if off_items:
            excluded_parts.append(",".join(off_items))
        root.title("알람 [제외: " + " | ".join(excluded_parts) + "]")

    def on_filter_changed():
        update_title()
        refresh_visible_rows()

    dir_vars = {"BULL": tk.BooleanVar(value=True), "BEAR": tk.BooleanVar(value=True)}
    tk.Checkbutton(filter_frame, text="Bull", variable=dir_vars["BULL"], fg="#c98a1a", command=on_filter_changed).pack(side="left")
    tk.Checkbutton(filter_frame, text="Bear", variable=dir_vars["BEAR"], fg="#2a5db0", command=on_filter_changed).pack(side="left", padx=(0, 10))

    # 종목 체크박스는 신호가 처음 들어올 때마다 동적으로 하나씩 추가됩니다
    # (대시보드의 종목 필터가 동적으로 늘어나는 것과 동일한 방식).
    item_filter_frame = tk.Frame(filter_frame)
    item_filter_frame.pack(side="left")
    item_vars = {}  # 종목명 -> tk.BooleanVar

    def ensure_item_filter(item_name):
        if not item_name or item_name in item_vars:
            return
        var = tk.BooleanVar(value=True)
        item_vars[item_name] = var
        tk.Checkbutton(item_filter_frame, text=item_name, variable=var, command=on_filter_changed).pack(side="left")

    def passes_filter(item):
        kind = item.get("kind", "")
        direction = "BULL" if kind.startswith("BULL") else ("BEAR" if kind.startswith("BEAR") else None)
        if direction and not dir_vars[direction].get():
            return False
        item_name = item.get("item", "")
        ensure_item_filter(item_name)
        if item_name in item_vars and not item_vars[item_name].get():
            return False
        return True

    # [2026-07-21 추가][필터가 "이미 떠있는 행"도 실시간으로 걸러내게 수정]
    # 예전엔 체크박스가 "이후 도착하는 신호"만 막아서, 체크박스를 껐다 켜도
    # 이미 표에 떠있는 행은 그대로 안 바뀌었습니다. 모든 행의 필터판정용
    # 데이터(kind/item)를 계속 기억해뒀다가, 체크박스가 바뀔 때마다 전체를
    # 다시 훑어서 tree.detach()/tree.move()로 보이기/숨기기를 다시 계산합니다.
    row_filter_data = {}  # iid -> {"kind":.., "item":..}
    row_order = []        # 삽입 순서(최신이 앞) - 다시 보일 때 원래 위치로 복구하기 위함

    def refresh_visible_rows():
        attached = set(tree.get_children(""))
        display_idx = 0
        for iid in row_order:
            if not tree.exists(iid):
                continue
            meta = row_filter_data.get(iid, {})
            should_show = passes_filter(meta)
            is_attached = iid in attached
            if should_show:
                tree.move(iid, "", display_idx)
                display_idx += 1
            elif is_attached:
                tree.detach(iid)
        if sort_state["col"]:
            apply_sort()
        restripe_rows()

    # ---------- [2026-07-17 추가][작업표시줄 최소화 대응] ----------
    # "닫기" 버튼(close_window)으로 숨긴 경우(withdrawn 상태)엔 기존
    # 동작 그대로 - 다음 신호가 오면 자동으로 다시 나타납니다(MT5 스타일).
    # 하지만 사용자가 윈도우 자체의 최소화(_) 버튼으로 작업표시줄에
    # 내려놓은 경우(iconic 상태)는 다릅니다 - 이때는 새 신호가 와도
    # 강제로 창을 다시 띄우지 않고, 작업표시줄 아이콘만 깜빡이게(+소리는
    # 그대로) 해서, 사용자가 직접 클릭해야만 창이 앞으로 나옵니다.
    def is_minimized():
        try:
            return root.state() == "iconic"
        except Exception:
            return False

    def flash_taskbar():
        # Windows 전용 API(user32.FlashWindowEx)를 ctypes로 직접 호출합니다.
        #
        # [2026-07-17 버그 수정] tkinter의 root.winfo_id()가 돌려주는
        # 핸들은 실제로 작업표시줄에 뜨는 "최상위 프레임 창"이 아니라,
        # 그 안의 내부(자식) 드로잉 영역의 핸들인 경우가 있습니다.
        # FlashWindowEx에 그 핸들을 그대로 넘기면 API 호출 자체는
        # 성공하는 것처럼 보여도 실제로는 아무 효과가 없습니다(사용자가
        # 실제로 겪은 "소리는 나는데 안 깜빡임" 증상이 바로 이것 -
        # 예전엔 except로 실패를 조용히 삼켜서 원인 확인도 안 됐음).
        # 이제는 GetAncestor(hwnd, GA_ROOT)로 그 핸들의 진짜 최상위
        # 조상 창을 먼저 찾아서, 그 창을 깜빡입니다. 그리고 실패하면
        # (윈도우가 아니거나 API 호출 자체가 실패하면) 알림 흐름을
        # 막지는 않되, 콘솔에 원인을 남겨서 다음에 진단할 수 있게 합니다.
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.GetAncestor.restype = wintypes.HWND
            user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
            user32.FlashWindowEx.restype = wintypes.BOOL

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("hwnd", wintypes.HWND),
                    ("dwFlags", wintypes.DWORD),
                    ("uCount", wintypes.UINT),
                    ("dwTimeout", wintypes.DWORD),
                ]

            FLASHW_ALL = 3          # 창 테두리 + 작업표시줄 버튼 둘 다 깜빡임
            FLASHW_TIMERNOFG = 12   # 사용자가 창을 클릭해서 앞으로 가져올 때까지 계속 깜빡임
            GA_ROOT = 2             # 최상위 조상 창을 찾는 옵션

            child_hwnd = wintypes.HWND(root.winfo_id())
            top_hwnd = user32.GetAncestor(child_hwnd, GA_ROOT)
            if not top_hwnd:
                top_hwnd = child_hwnd  # 못 찾으면 원래 핸들로라도 시도

            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), top_hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0)
            ok = user32.FlashWindowEx(ctypes.byref(info))
            if not ok:
                print("[알람창][진단] FlashWindowEx가 실패를 반환했습니다 "
                      "(child_hwnd=" + str(root.winfo_id()) + ", top_hwnd=" + str(top_hwnd) + ")")
        except Exception as e:
            print("[알람창][진단] 작업표시줄 깜빡임 호출 중 오류:", e)

    table_frame = tk.Frame(root)
    table_frame.pack(fill="both", expand=True, padx=4, pady=4)

    columns = ("achieve", "kst", "item", "tf", "kind", "price", "contract")
    column_labels = {
        "achieve": "달성", "kst": "서버시간", "item": "종목", "contract": "월물",
        "tf": "타임프레임", "kind": "신호", "price": "가격",
    }
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
    tree.column("achieve", width=36, minwidth=36, anchor="center", stretch=False)
    tree.column("kst", width=145, anchor="w")
    tree.column("item", width=34, minwidth=34, anchor="center", stretch=False)
    tree.column("tf", width=75, anchor="w")
    tree.column("kind", width=48, minwidth=48, anchor="center", stretch=False)
    tree.column("price", width=80, anchor="e")
    tree.column("contract", width=55, anchor="center")

    # [2026-07-17 추가][정렬 기능] 대시보드처럼, 표 머리글을 클릭하면 그
    # 칼럼 기준으로 정렬되고, 같은 칼럼을 다시 클릭하면 방향이 뒤집힙니다.
    # 아직 한 번도 클릭 안 한 기본 상태(sort_state["col"] is None)에서는
    # 예전처럼 "최신 신호가 맨 위"로 그대로 쌓입니다.
    sort_state = {"col": None, "reverse": False}

    def sort_key_for(iid, col):
        vals = tree.item(iid, "values")
        raw = vals[columns.index(col)]
        if col == "price":
            try:
                return float(str(raw).replace(",", ""))
            except Exception:
                return 0.0
        if col == "achieve":
            # [2026-07-16에 만든 규칙과 동일] 감시중(대기중/빠짐/미확인)이
            # 항상 먼저 오고, 확정된(달성/무효) 것이 나중에 오도록 순위를
            # 매깁니다. 대시보드의 cmpByKey와 같은 취지입니다.
            state = row_achieve_state.get(iid)
            return 1 if state in ("achieved", "invalid") else 0
        return raw

    def update_column_headers():
        for c in columns:
            label = column_labels[c]
            if sort_state["col"] == c:
                label += " \u25bc" if sort_state["reverse"] else " \u25b4"
            tree.heading(c, text=label, command=lambda cc=c: sort_by_column(cc))

    def apply_sort():
        col = sort_state["col"]
        if not col:
            return
        children = list(tree.get_children(""))
        children.sort(key=lambda iid: sort_key_for(iid, col), reverse=sort_state["reverse"])
        for idx, iid in enumerate(children):
            tree.move(iid, "", idx)
        restripe_rows()

    def sort_by_column(col):
        if sort_state["col"] == col:
            sort_state["reverse"] = not sort_state["reverse"]
        else:
            sort_state["col"] = col
            sort_state["reverse"] = False
        update_column_headers()
        apply_sort()

    update_column_headers()  # 초기 헤더 텍스트 설정 + 클릭 핸들러 연결

    # [2026-07-16 추가] 나중에 달성/무효 판정이 오면, 어느 행을 갱신해야
    # 하는지 빠르게 찾기 위한 매핑입니다. 키는 원래 신호를 특정하는
    # (종목, 타임프레임, 날짜, 시각, 가격) 조합 - STATUS_ACHIEVED/
    # STATUS_INVALID 줄도 이 5개 값은 원래 신호와 동일하게 실려옵니다.
    row_by_key = {}
    # [신규][2026-09-23][프레임밀림 표시] REGISTERED 이벤트의 source 필드에
    # 실려오는 FRAME_SHIFT_SUSPECT:disp=X;actual=Y를 여기 저장해뒀다가,
    # 같은 신호의 실제 행(BULL/BEAR)을 만들 때 타임프레임 칸에
    # "M0002(M0001)"(표시(실제#주기)) 형식으로 붙여준다.
    registered_source_by_key = {}
    _FRAME_SHIFT_RE = re.compile(r"FRAME_SHIFT_SUSPECT:disp=(\d+)[;_]actual=(\d+)")

    def make_row_key(d):
        # [2026-07-19 버그 수정] contract(월물)를 안 넣으면, 서로 다른
        # 월물의 신호가 우연히 item/label/date/time/price까지 전부 같으면
        # (극히 드물지만 이론상 가능) row_by_key에서 서로 덮어써서 엉뚱한
        # 행의 달성/무효가 갱신되는 문제가 있었습니다(알림창 로직을
        # 가짜 tkinter로 실제 실행시켜 테스트하다가 발견함). contract를
        # 키에 포함시켜 완전히 분리합니다.
        return (d.get("item", ""), d.get("contract", ""), d.get("label", ""), d.get("date", ""), d.get("time", ""), d.get("price", ""))

    # [스크롤바] 알림이 많이 쌓여도 다 보이도록
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    # [한 줄 건너 배경색] 회색/흰색을 번갈아 넣어서 줄 구분이 잘 되게 합니다.
    tree.tag_configure("evenrow", background="#f0f0f0")
    tree.tag_configure("oddrow", background="white")
    # [2026-07-16 추가] 달성/무효가 갱신된 행은 글자색으로 한눈에 구분되게
    # (배경색은 위 evenrow/oddrow가 계속 담당 - 태그를 같이 적용해서
    # 배경과 글자색이 겹치지 않고 둘 다 적용됩니다)
    tree.tag_configure("achieved", foreground="#1a7f37")  # 초록 - 달성
    tree.tag_configure("invalid", foreground="#b42318")   # 빨강 - 무효
    # [2026-07-16 추가] 대시보드의 ⏳/⚠️와 색상 의미를 맞춤(일관성 유지)
    tree.tag_configure("waiting", foreground="")   # [수정][2026-09-29][사용자 요청] 회색 강제 대신 기본 글자색 그대로 - 정상 대기중
    tree.tag_configure("missing", foreground="#c9770a")   # 주황 - 감시목록에서 빠짐
    # [2026-07-23 추가] STATUS_RETRACTED - 정확도점검이 authoritative
    # 데이터로 재검증한 결과 애초에 신호가 아니었음이 확인된 경우.
    # 달성/무효/대기중/빠짐 어디에도 안 섞이게 보라색으로 별도 구분.
    # [제거][사용자 요청][철회기능 전체 제거] "retracted" 태그(보라색) 삭제됨(더 이상 어떤 행에도 안 붙음)
    # [2026-08-26 추가][대시보드 일관성] 대시보드는 복원된 신호를 주황빛
    # 강조(drop-shadow)로 표시하는데, 이 알람창엔 그 표시가 아예 없었다
    # (구조검증으로 확인된 실제 불일치). foreground를 안 건드리는 별도
    # 속성(굵은글씨)을 써서, 달성/무효/대기 등 기존 색상표시와 절대
    # 안 겹치면서(다른 tkinter 속성이라 동시적용됨) 강조만 더한다.
    tree.tag_configure("restored", font=("TkDefaultFont", 9, "bold"))
    row_restored = {}  # iid -> True (복원된 신호만 기록)
    row_achieve_state = {}  # iid -> "achieved" | "invalid" | "waiting" | "missing" | "retracted"

    # [2026-09-25 신규][무제한 누적 방지] 이 알람창은 "계속 켜둔 채로" 쓰는
    # 프로그램이라, 행 수 상한이 없으면 tree와 row_by_key/row_meta/
    # row_filter_data/row_achieve_state/row_restored가 장시간(며칠) 켜둘수록
    # 끝없이 커진다(실제로 대시보드 쪽 liveBarMismatchGroups에서 겪었던 것과
    # 동일한 유형의 메모리 누수) - 최근 MAX_ALERT_ROWS건만 남기고, 넘으면
    # row_order 맨 뒤(가장 오래된 행)부터 tree와 관련된 모든 자료구조를 한
    # 함수에서 같이 정리한다(한쪽만 지워서 불일치가 생기는 걸 원천 차단 -
    # 대시보드가 v1.47에서 rowsByKey로 통합한 것과 같은 원칙).
    MAX_ALERT_ROWS = 200
    row_key_by_iid = {}  # iid -> row_by_key에 쓴 key (오래된 행 정리시 역참조용)

    def evict_old_rows():
        while len(row_order) > MAX_ALERT_ROWS:
            old_iid = row_order.pop()  # row_order는 "최신이 맨 앞"이라 맨 뒤가 가장 오래된 행
            if tree.exists(old_iid):
                tree.delete(old_iid)
            row_meta.pop(old_iid, None)
            row_filter_data.pop(old_iid, None)
            row_achieve_state.pop(old_iid, None)
            row_restored.pop(old_iid, None)
            old_key = row_key_by_iid.pop(old_iid, None)
            if old_key is not None and row_by_key.get(old_key) == old_iid:
                del row_by_key[old_key]

    # [2026-07-16 추가] 대시보드와 동일한 방식으로 "지금 감시 중인 신호
    # 목록"을 소스(분봉/틱봉)별·종목별로 저장해둡니다. HEARTBEAT_MIN/
    # HEARTBEAT_TICK을 label로 구분해서 서로 덮어쓰지 않게 합니다
    # (대시보드에서 겪었던 "분봉/틱봉 하트비트가 번갈아 서로를 덮어써서
    # 표시가 깜빡이던 버그"와 동일한 함정이라 처음부터 분리해서 설계).
    # [2026-07-19 버그 수정] 종목명만으로 키를 만들면, 같은 종목의 서로
    # 다른 월물(예: 나스닥 U26과 Z26)의 하트비트가 서로를 덮어써버립니다
    # - 나중에 온 월물의 감시목록으로 앞선 월물의 대기중/빠짐 판정을
    # 잘못 계산하게 됨(월물 칼럼을 추가하며 뒤늦게 발견). "종목|월물"
    # 조합으로 키를 만들어서 이 문제를 없앱니다.
    last_pending_keys = {"min": {}, "tick": {}}
    last_pending_keys_received = {"min": {}, "tick": {}}
    # [신규][2026-09-29][대시보드와 판정기준 통일] 대시보드(effectiveAchieveStatus,
    # 2026-08-11 근본수정)는 "가장 최근 하트비트가 이 신호의 실제 등록시각보다
    # 이전이면 missing이 아니라 unknown(판단 근거 없음)"으로 처리하는데, 이
    # 알람창의 refresh_wait_missing_marks()엔 그 로직이 아예 없어서 - 봉
    # 시각(date/time)은 되짚기(lf1/lf2)로 과거일 수 있는데 실제 등록은 방금
    # 이라 그 사이 하트비트가 아직 안 왔을 뿐인 경우까지 곧장 ⚠️(missing)로
    # 잘못 표시됐다(사용자가 FRAME_SHIFT_SUSPECT 표시 신호에서 실측 - 대시보드는
    # ⏳인데 알람창만 ⚠️). SAVE_SCHEDULED의 eventTime(실제 처리시각)과 각
    # 소스(분봉/틱봉)의 최신 하트비트 시각을 같이 기억해뒀다가 비교한다.
    last_heartbeat_time = {"min": {}, "tick": {}}  # scope_key -> "YYYYMMDD HH:MM:SS"
    real_reg_time_by_pk = {}  # "label|kind|date|time|price" -> "YYYYMMDD HH:MM:SS"(SAVE_SCHEDULED eventTime)
    # iid -> {item, contract, tf, kind, date, time, price} (아직 미결인 행들만
    # - 나중에 하트비트가 올 때마다 이 정보로 대기중/빠짐을 다시 계산하기 위함)
    row_meta = {}

    def pending_source(tf):
        return "tick" if tf.startswith("T") else "min"

    def pending_scope_key(item_name, contract):
        return item_name + "|" + (contract or "")

    def make_pending_key(d):
        return f'{d.get("label","")}|{d.get("kind","")}|{d.get("date","")}|{d.get("time","")}|{d.get("price","")}'

    def restripe_rows():
        # 맨 위(최신)에 새 줄을 끼워넣는 방식이라, 넣을 때마다 전체 줄의
        # 홀/짝이 한 칸씩 밀립니다. 그래서 매번 전체를 다시 훑어서
        # 태그를 다시 매겨줘야 줄무늬가 항상 정확하게 유지됩니다.
        # [2026-07-16 수정] 달성/무효로 표시된 행은 그 색깔 태그도 같이
        # 유지해야 해서, 단순히 evenrow/oddrow로만 덮어쓰지 않고 같이 붙입니다.
        for idx, iid in enumerate(tree.get_children()):
            stripe = "evenrow" if idx % 2 == 0 else "oddrow"
            achieve_tag = row_achieve_state.get(iid)
            tags = [stripe]
            if achieve_tag:
                tags.append(achieve_tag)
            if row_restored.get(iid):
                tags.append("restored")
            tree.item(iid, tags=tuple(tags))

    def close_window():
        # 완전히 없애지 않고 숨기기만 합니다 - 이력(표)은 그대로 남아있다가
        # 다음 알림이 오면 다시 나타납니다 (MT5처럼 이력이 유지되는 방식)
        root.withdraw()

    close_btn = tk.Button(root, text="닫기", command=close_window, width=10)
    close_btn.pack(pady=(0, 6))

    # 창의 X 버튼을 눌러도 프로그램이 통째로 죽지 않고, 위와 동일하게
    # "숨기기"만 하도록 합니다 (완전 종료는 브릿지 자체를 끌 때만).
    root.protocol("WM_DELETE_WINDOW", close_window)

    def refresh_wait_missing_marks():
        # [2026-07-16 추가] 하트비트가 새로 올 때마다, 아직 달성/무효가
        # 안 난 모든 행을 대시보드와 똑같은 기준으로 다시 계산합니다:
        #   - 그 종목·소스(분봉/틱봉)의 감시 목록에 이 신호 키가 있으면
        #     -> ⏳(정상 대기중)
        #   - 하트비트는 받았는데 그 목록엔 없으면 -> ⚠️(감시목록에서 빠짐)
        #   - 그 종목·소스의 하트비트를 아직 한 번도 못 받았으면 -> 그대로 둠(빈 칸)
        changed = False
        for iid, meta in list(row_meta.items()):
            if row_achieve_state.get(iid) in ("achieved", "invalid"):
                continue  # 이미 확정된 행은 건드리지 않음
            if not tree.exists(iid):
                del row_meta[iid]
                continue
            source = pending_source(meta.get("label", ""))
            item_name = meta.get("item", "")
            scope_key = pending_scope_key(item_name, meta.get("contract", ""))
            if not last_pending_keys_received[source].get(scope_key):
                continue  # 아직 판단할 근거 없음 - 빈 칸 유지
            key_set = last_pending_keys[source].get(scope_key, set())
            pk = make_pending_key(meta)
            if pk in key_set:
                new_state = "waiting"
            else:
                # [신규][2026-09-29][대시보드와 판정기준 통일, 2026-08-11
                # 대시보드 근본수정과 동일 원리] 봉 시각(date/time)은
                # 되짚기(lf1/lf2)로 과거일 수 있어도 실제 등록은 방금일 수
                # 있다 - 그 사이 하트비트가 아직 한 번도 안 돌았을 뿐인데
                # 곧장 missing(⚠️)으로 단정하면 안 된다. SAVE_SCHEDULED의
                # 실제 처리시각(eventTime)보다 "가장 최근 하트비트 시각"이
                # 더 이전이면(=아직 이 신호를 볼 기회가 없었던 하트비트),
                # 대시보드의 unknown과 동일하게 취급한다 - 대시보드는 unknown도
                # waiting과 같은 ⏳/회색을 그대로 재사용(불투명도만 다르게)하므로,
                # 이 알람창도 같은 아이콘/색(waiting 태그)으로 표시해 일관성을
                # 맞춘다(사용자 요청: "대시보드와 동일하게, 글씨색은 회색으로").
                reg_time = real_reg_time_by_pk.get(pk)
                hb_time = last_heartbeat_time[source].get(scope_key)
                if reg_time and hb_time and hb_time < reg_time:
                    new_state = "waiting"
                else:
                    new_state = "missing"
            if row_achieve_state.get(iid) != new_state:
                row_achieve_state[iid] = new_state
                mark = "⏳" if new_state == "waiting" else "⚠️"
                vals = list(tree.item(iid, "values"))
                vals[0] = mark
                tree.item(iid, values=vals)
                changed = True
        if changed:
            restripe_rows()

    def poll_queue():
        try:
            while True:
                item = alert_queue.get_nowait()
                kind = item.get("kind", "")

                # [근본수정][2026-09-10][STATS_IMMEDIATE 오염 방어] 실제
                # 화면에서 "STATS_IMMEDIATE" 문자열이 종목/서버시간 등
                # 엉뚱한 칸에 섞여 나오는 깨진 행이 확인됨. 정확한 원인
                # (어느 단계에서 필드가 밀리는지)은 아직 못 찾았지만,
                # _NON_ALERT_KINDS에 STATS_IMMEDIATE를 넣어둔 원래 의도
                # (이 알람창엔 절대 안 뜨게)를 다시 한번 못박기 위해,
                # 어느 필드에 이 문자열이 섞여 있든 통째로 무시한다.
                if any(str(v) == "STATS_IMMEDIATE" for v in item.values()):
                    continue

                # [2026-07-16 추가] HEARTBEAT_MIN/HEARTBEAT_TICK: 새 행을
                # 추가하지 않고, "지금 감시 중인 신호 키 목록"만 저장해둔
                # 뒤 대기중/빠짐 표시를 갱신합니다.
                if kind == "HEARTBEAT":
                    pk_str = item.get("pendingKeys")
                    if pk_str is not None:
                        source = "tick" if item.get("label") == "HEARTBEAT_TICK" else "min"
                        key_set = set(pk_str.split(";")) if pk_str else set()
                        scope_key = pending_scope_key(item.get("item", ""), item.get("contract", ""))
                        last_pending_keys[source][scope_key] = key_set
                        last_pending_keys_received[source][scope_key] = True
                        # [신규][2026-09-29] missing 오판정 방지용 - 이 하트비트
                        # 자체의 서버시각(이 줄의 date/time 필드, 실제 처리시각)을
                        # 기억해둔다. 형식이 SAVE_SCHEDULED의 eventTime과 동일한
                        # "YYYYMMDD HH:MM:SS"라 문자열 비교만으로 선후 판단 가능.
                        hb_date = item.get("date", "")
                        hb_time = item.get("time", "")
                        if hb_date and hb_time:
                            last_heartbeat_time[source][scope_key] = hb_date + " " + hb_time
                        refresh_wait_missing_marks()
                    continue

                # [2026-08-03 추가] GAP_CHECK는 데스크탑 알림창 표에 넣을
                # 대상이 아님(원래 alert_queue에 안 들어가지만 방어적으로 처리).
                if kind == "GAP_CHECK":
                    continue

                # [신규][2026-09-23][프레임밀림 표시] REGISTERED 이벤트는
                # 원래도 알람 행을 새로 만들지 않는 메타데이터 줄이다 -
                # source 필드만 저장해두고 넘어간다(나중에 이 신호의 진짜
                # BULL/BEAR 행을 만들 때 타임프레임 칸에 참고).
                if kind == "REGISTERED":
                    registered_source_by_key[make_row_key(item)] = item.get("source", "")
                    continue

                # [신규][2026-09-29][missing 오판정 근본수정 - 대시보드와 통일]
                # SAVE_SCHEDULED는 신호가 실제로(하트비트 대기 없이 즉시) 처리된
                # 진짜 서버시각(eventTime)을 담고 있다 - refresh_wait_missing_marks
                # 가 "이 신호를 볼 기회가 아직 없었던 하트비트"와 "정말 감시목록
                # 에서 빠진 것"을 구분하는 데 쓴다. 대시보드(saveTrackingByPk)와
                # 동일하게 진짜 신호종류(signalKind, 8번째 필드)가 있으면 그걸
                # pk의 kind로 쓰고, 없으면(구버전 로그) 이 줄 자신의 kind로 폴백.
                if kind in ("SAVE_SCHEDULED", "SAVE_QUEUED", "SAVE_CONFIRMED"):
                    event_time = item.get("eventTime")
                    if event_time:
                        real_kind = item.get("signalKind") or item.get("kind", "")
                        reg_pk = "{}|{}|{}|{}|{}".format(
                            item.get("label", ""), real_kind, item.get("date", ""),
                            item.get("time", ""), item.get("price", ""))
                        real_reg_time_by_pk[reg_pk] = event_time
                    continue

                # [2026-07-16 추가] 달성/무효 판정 결과는 새 행을 추가하는 게
                # 아니라, 이미 떠있는 원래 신호 행을 찾아서 "달성" 칸과
                # 글자색만 갱신합니다. 알람창을 계속 띄워둔 상태라면 실시간
                # 으로 바로 바뀌는 걸 볼 수 있습니다. (그 행이 알람창에 없으면
                # - 억제됐거나 너무 오래돼서 등 - 업데이트할 대상이 없으니
                # 조용히 무시합니다)
                if kind in ("STATUS_ACHIEVED", "STATUS_INVALID"):
                    key = make_row_key(item)
                    iid = row_by_key.get(key)
                    if iid and tree.exists(iid):
                        if kind == "STATUS_ACHIEVED":
                            mark = "✅"
                            new_state = "achieved"
                        else:  # STATUS_INVALID
                            mark = "❌"
                            new_state = "invalid"
                        vals = list(tree.item(iid, "values"))
                        vals[0] = mark
                        tree.item(iid, values=vals)
                        row_achieve_state[iid] = new_state
                        row_meta.pop(iid, None)  # 확정됐으니 더 이상 대기중/빠짐 재계산 대상 아님
                        # [2026-07-17 추가] "달성" 칼럼 기준으로 정렬 중이었다면,
                        # 방금 확정된 이 행의 순위가 바뀌었을 수 있으니 다시 정렬합니다.
                        if sort_state["col"]:
                            apply_sort()
                        else:
                            restripe_rows()
                    continue

                # [2026-07-21 수정][필터가 실시간으로 목록을 다시 걸러내게
                # 변경] 예전엔 필터에 안 걸리면 아예 표에 넣지도 않아서,
                # 나중에 체크박스를 다시 켜도 그 신호는 영영 안 보였습니다.
                # 이제는 항상 표에 넣어두되(row_filter_data/row_order에
                # 기억해둠), 지금 필터를 안 통과하면 화면에서만 숨깁니다
                # (tree.detach) - 체크박스를 다시 켜면 refresh_visible_rows가
                # 이 신호를 정확히 원래 자리에 다시 보여줍니다. 팝업/소리는
                # 지금 필터를 통과하는 경우에만 울립니다(꺼둔 종목/방향까지
                # 시끄럽게 알릴 필요는 없으니까요).
                currently_passes = passes_filter(item)

                # [2026-07-15 수정] 예전엔 "한국시간"이라고 라벨을 붙여놓고
                # 실제로는 변환 없이 서버(시카고) 원본 시각을 보여주고
                # 있어서 라벨과 실제 값이 안 맞았습니다. 대시보드의
                # "서버시간(시카고)" 열과 똑같은 형식으로 맞추고, 라벨도
                # "서버시간"으로 고쳤습니다. (진짜 한국시간이 필요하면
                # 대시보드의 "한국시간(KST)" 열을 참고하시면 됩니다.)
                server_str = f'{item.get("date", "")} {item.get("time", "")}'
                # [2026-08-26 추가][대시보드 일관성] 대시보드는 복원된 신호의
                # 아이콘 자체를 바꾸지 않고 그 위에 주황빛 강조(glow)만
                # 얹는다(달성상태 아이콘은 그대로 유지). 여기서도 "달성"
                # 칸 텍스트는 그대로 두고(나중에 ⏳/⚠️/✅ 등으로 계속
                # 갱신됨) row_restored로만 표시해서, 굵은글씨 태그가
                # restripe_rows()를 통해 항상 같이 유지되게 한다 - 칸
                # 텍스트에 직접 넣으면 다음 갱신 때 덮어써져 사라진다.
                is_restored = bool(item.get("wasRestored"))
                # [신규][2026-09-23][프레임밀림 표시] 같은 신호의 REGISTERED
                # 이벤트에서 저장해둔 source에 FRAME_SHIFT_SUSPECT가 있으면
                # 타임프레임 칸을 "M0002(M0001)"(표시(실제#주기)) 형식으로.
                display_label = item.get("label", "")
                _fs_src = registered_source_by_key.get(make_row_key(item), "")
                _fs_m = _FRAME_SHIFT_RE.search(_fs_src) if _fs_src else None
                if _fs_m:
                    _fs_prefix = display_label[:1] if display_label else ""  # M 또는 T
                    display_label = "⚠" + _fs_prefix + _fs_m.group(2).zfill(4)  # [수정][사용자 요청] "M0002(M0001)" -> "⚠M0001"
                # [신규][2026-09-23][사용자 요청] 종목칸을 넓게 차지하던 전체
                # 이름(NASDAQ100/SP500/GOLD) 대신 한 글자(N/S/G)만 표시 -
                # 목록에 없는 새 종목이 추가돼도 안 깨지게, 없으면 앞글자로 폴백.
                _item_abbr_map = {"NASDAQ100": "N", "SP500": "S", "GOLD": "G"}
                _item_full = item.get("item", "")
                _item_abbr = _item_abbr_map.get(_item_full, _item_full[:1] if _item_full else "")
                iid = tree.insert("", 0, values=(
                    "", server_str, _item_abbr, display_label,
                    item.get("kind", ""), item.get("price", ""), item.get("contract", "")
                ))  # 최신이 맨 위로 ("달성" 칸은 처음엔 빈 값), 월물은 맨 마지막 칸
                if is_restored:
                    row_restored[iid] = True
                _row_key = make_row_key(item)
                row_by_key[_row_key] = iid  # [2026-07-16] 나중에 달성/무효 갱신할 때 이 행을 찾기 위해 기억
                row_key_by_iid[iid] = _row_key  # [2026-09-25] 오래된 행 정리(evict_old_rows)시 역참조용
                row_meta[iid] = {
                    "item": item.get("item", ""), "contract": item.get("contract", ""), "label": item.get("label", ""),
                    "kind": item.get("kind", ""), "date": item.get("date", ""),
                    "time": item.get("time", ""), "price": item.get("price", ""),
                }  # [2026-07-16] 대기중/빠짐 재계산용
                # [2026-07-21 추가] 필터 재판정용 데이터도 같이 기억.
                # row_order는 "최신이 맨 앞"이 되도록 앞에 끼워넣습니다.
                row_filter_data[iid] = {"kind": item.get("kind", ""), "item": item.get("item", "")}
                row_order.insert(0, iid)
                # [2026-09-25 신규][무제한 누적 방지] 방금 추가로 MAX_ALERT_ROWS를
                # 넘었으면 가장 오래된 행부터 바로 정리한다.
                evict_old_rows()
                if not currently_passes:
                    tree.detach(iid)
                # [2026-07-17 추가] 정렬 기준이 걸려있으면(사용자가 헤더를
                # 클릭해서 정렬 중이면) 새로 들어온 행도 그 기준에 맞춰
                # 다시 정렬합니다. 정렬 기준이 없으면(기본 상태) 예전처럼
                # 맨 위(최신순)에 그대로 둡니다.
                if sort_state["col"]:
                    apply_sort()
                else:
                    restripe_rows()
                if not currently_passes:
                    continue  # 필터에 안 맞으면 여기서 멈춤 - 팝업/소리 없음
                play_alert_sound()
                # [2026-07-17 수정][작업표시줄 최소화 대응] 사용자가 윈도우
                # 자체의 최소화 버튼으로 작업표시줄에 내려놓은 상태(iconic)
                # 라면, 강제로 다시 띄우지 않고 작업표시줄 아이콘만
                # 깜빡이게 합니다(소리는 위에서 이미 남). 사용자가 직접
                # 작업표시줄을 클릭해야만 창이 앞으로 나옵니다. "닫기"
                # 버튼으로 숨긴 경우(withdrawn)는 기존처럼 자동으로
                # 다시 나타납니다(is_minimized()가 False를 돌려줌).
                if is_minimized():
                    flash_taskbar()
                else:
                    root.deiconify()  # 숨겨져 있었다면 다시 보이게
                    root.lift()       # 다른 창들보다 앞으로
                    root.attributes("-topmost", True)
        except queue.Empty:
            pass
        root.after(200, poll_queue)  # 200ms마다 반복 확인

    root.after(200, poll_queue)
    root.mainloop()

async def main():
    if os.path.exists(STOP_FLAG):
        try: os.remove(STOP_FLAG)
        except Exception: pass

    if ENABLE_DESKTOP_ALERT:
        # tkinter는 자기만의 mainloop을 돌려야 해서, asyncio랑 같은
        # 스레드에서 못 돌립니다. daemon=True로 만들어서, 브릿지 메인
        # 프로그램이 끝나면 이 스레드도 같이 자동 정리되게 합니다.
        alert_thread = threading.Thread(target=start_alert_window, daemon=True)
        alert_thread.start()

    async with websockets.serve(handler, "localhost", WS_PORT):
        print(f"브릿지 서버 시작됨: ws://localhost:{WS_PORT}")
        print("이 창을 끄지 말고 켜두세요. 종료하려면 Ctrl+C 를 누르세요.")
        await tail_loop()

if __name__ == "__main__":
    asyncio.run(main())
