# -*- coding: utf-8 -*-
"""
================================================================================
[프로젝트 개요 - 새 대화창에서 이 파일을 처음 보는 경우를 위한 전체 설명]

이 파일의 역할:
  yesspot_signals_dashboard_txt.html(실시간 신호 목록 웹페이지)을
  http://localhost:8081 으로 서빙하는 아주 단순한 정적 파일 웹서버.
  (이 폴더 안의 어떤 파일이든 http://localhost:8081/파일명 으로 열림)

전체 시스템 구조:
  [예스스팟 전략 6개] -> [yesspot_signals.txt] -> [bridge_signals_txt.py]
    -> WebSocket(9101) -> [yesspot_signals_dashboard_txt.html]
       (이 html을 실제로 브라우저에 띄워주는 역할이 바로 이 파일: dashboard_server.py, 포트 8081)

[종료 방식]
  bridge_signals_txt.py가 대시보드의 "대시보드 종료" 버튼 클릭을 받으면
  stop.flag 파일을 만듭니다. 이 파일은 그 stop.flag 파일이 생기는 것을
  1초 간격으로 감시하다가, 생기면 자기 자신도 즉시 종료합니다.
  (브릿지와 웹서버 둘 다 한 번의 클릭으로 깔끔하게 같이 꺼지게 하기 위함)

[함께 필요한 파일들 - 전부 같은 폴더에 있어야 함]
  bridge_signals_txt.py
  yesspot_signals_dashboard_txt.html
  start_yesspot_dashboard.bat (이 파일 + bridge_signals_txt.py를 한번에 실행)

[사용 방법] python dashboard_server.py  (계속 켜둔 채로 사용)
================================================================================
"""

import http.server
import socketserver
import threading
import os
import time
import sys
import functools

PORT = 8081  # [텍스트버전] 엑셀버전 웹서버(8080)와 동시에 켜도 충돌하지 않게 다른 포트
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STOP_FLAG = os.path.join(SCRIPT_DIR, "stop.flag")

if os.path.exists(STOP_FLAG):
    try:
        os.remove(STOP_FLAG)
    except Exception:
        pass

# [2026-09-25 수정][서빙 루트가 cwd에 의존하던 문제 수정] directory 인자가
# 없으면 SimpleHTTPRequestHandler는 프로세스의 현재 작업디렉터리를 그대로
# 서빙 루트로 쓴다 - 배치파일 등에서 다른 작업폴더로 실행되면 대시보드 html을
# 못 찾는다. STOP_FLAG와 동일하게 이 스크립트 자신의 폴더(SCRIPT_DIR)를
# 명시적으로 서빙 루트로 고정한다.
Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SCRIPT_DIR)

# [2026-09-25 수정][포트 점유시 무진단 크래시 방지] 8081 포트가 이미 사용
# 중이면(예: 이전 실행이 완전히 안 꺼지고 남아있는 경우) 예외처리가 없어
# 원인을 알 수 없는 트레이스백만 찍고 죽었다 - 사용자가 바로 원인을 알 수
# 있게 명확한 한글 메시지를 띄우고 정상 종료한다.
try:
    httpd = socketserver.TCPServer(("", PORT), Handler)
except OSError as e:
    print(f"!! 웹서버를 시작할 수 없습니다 (포트 {PORT}번이 이미 사용 중일 가능성이 높습니다): {e}")
    print("!! 이전에 켜둔 대시보드 웹서버 창(또는 python 프로세스)이 아직 안 꺼졌는지 먼저 확인해주세요.")
    sys.exit(1)
httpd.allow_reuse_address = True

def serve():
    httpd.serve_forever()

t = threading.Thread(target=serve, daemon=True)
t.start()

print(f"대시보드 웹서버 시작됨: http://localhost:{PORT}")
print("이 창을 끄지 말고 켜두세요.")
print("대시보드에서 '대시보드 종료' 버튼을 누르면 이 창도 자동으로 닫힙니다.")

try:
    while True:
        if os.path.exists(STOP_FLAG):
            print("종료 신호를 받았습니다. 웹서버를 닫습니다...")
            try:
                os.remove(STOP_FLAG)
            except Exception:
                pass
            os._exit(0)  # 즉시 프로세스 종료 (창도 함께 닫힘)
        time.sleep(1)
except KeyboardInterrupt:
    os._exit(0)
