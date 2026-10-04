# -*- coding: utf-8 -*-
"""
================================================================================
신호검색 자바파일(signal_*.js) 자동생성 스크립트

[이 파일의 역할]
config/contracts.json 에 정의된 종목/월물 정보를 바탕으로, 검증된 템플릿
2종(TICK/MIN)에서 실제 예스스팟 전략 파일을 찍어냅니다.
[2026-08-30 수정] 이 도구는 이제 next(다음월물)만 생성합니다 - 활성
월물은 이미 실시간으로 운영 중인 파일이라 이 도구로 다시 만들어
덮어쓸 이유가 없다는 지적에 따라 active 생성 자체를 없앴습니다.
워밍업 전용(PREWARM) 파일도 더 이상 필요 없어져 생성 대상에서
제외했습니다(관련 템플릿/함수 전부 제거).

[사용법]
    python3 generate_signal_files.py              # 전체 종목 next 재생성
    python3 generate_signal_files.py --slug nasdaq # 나스닥100만 next 재생성
      (--slug 뒤에는 contracts.json의 instruments 키: nasdaq/sp500/gold)

[새 월물로 넘어갈 때 해야 할 일 - 이제 이거 딱 하나뿐입니다]
    1. config/contracts.json 에서 해당 종목의 "next" 값을 다음다음 월물로
       갱신(예: nasdaq.active를 지금의 next 값으로, nasdaq.next를 그 다음
       분기물로)
    2. 이 스크립트 재실행
    3. generated/ 폴더에 새로 나온 파일을 예스스팟에 전략으로 등록하고,
       실제로 정상 동작 확인되면 그때 계약월 관리 페이지에서 이전
       활성월물을 "확인 및 삭제"로 정리

[왜 템플릿이 2종류인지]
    - TICK_TEMPLATE : 실시간 하이브리드 틱봉 버전 (지금 운영 중인 정식 버전)
    - MIN_TEMPLATE  : 분봉 버전

[핵심 설계 원칙 - 데이터 무결성]
    - 다음(next) 월물 파일만 생성합니다: 저장키에 월물 라벨을 붙여서
      (예: _Z26) 완전히 분리합니다. 다른 월물의 상태가 절대 섞여 들어올
      수 없습니다.
    - 종목명(item name, 로그의 첫 필드)은 활성/다음 월물 관계없이 항상
      기존과 동일(NASDAQ100/SP500/GOLD)로 유지합니다 - 대시보드 체크박스
      필터가 이 이름에 고정돼 있어서, 여기서 이름이 갈라지면 대시보드
      쪽도 같이 고쳐야 하는 범위 확장이 생깁니다. 대신 타임프레임 라벨
      접두사(T/P)와 저장키로 월물을 구분합니다.
================================================================================
[버전] 2026-10-04 v1.03
[버전관리 규칙] 이 파일을 수정할 때마다(사소한 수정 포함) 반드시 위 [버전]
  값을 소수점 둘째자리 기준으로 올리고(v1.00->v1.01->v1.02...) 아래
  [변경이력]에 한 줄 추가할 것.
[변경이력]
  v1.03 (2026-10-04): [텍스트버전] DASHBOARD_ROOT를 C:\dashboard_txt로 변경(그 외 로직 동일).
  v1.00 (~2026-08-10까지): 최초 버전(active+next+PREWARM 전부 생성)
  v1.01 (2026-08-30): [다음월물 전용화] 활성 월물은 이미 실시간 운영 중인
    파일이라 이 도구가 다시 만들어 덮어쓸 이유가 없다는 지적에 따라 active
    생성과 PREWARM_TEMPLATE 관련 코드를 전부 제거, next만 생성하도록 변경.
  v1.02 (2026-09-01): [예스스팟 스크립트 v1.10과 재동기화] 예스스팟 신호검색
    스크립트가 그동안 OUTPUT_FILE/DIAGNOSTIC_OUTPUT_FILE/PROGRESS_KEY/
    PENDING_STATE_KEY를 전부 MARKET_DATA_CODE/INSTRUMENT_NAME 두 값만으로
    스크립트 자신이 계산하는 구조로 바뀌었는데(v1.10), 이 생성기는 예전
    구조(하드코딩된 원본 리터럴을 일일이 찾아 치환) 그대로라 템플릿과
    어긋나 있었다. MARKET_DATA_CODE/INSTRUMENT_NAME 두 값만 정규식으로
    치환하도록 전면 단순화하고, 치환 전 템플릿이 예상 기준종목이 맞는지
    확인하는 안전장치(verify_template_baseline) 추가. MIN_TEMPLATE.js도
    나스닥이 아니라 금(GOLD/GCQ26) 기준으로 재생성(설계 문서와 일치시킴).
================================================================================
"""
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# [2026-07-19 신규][생성기와 대시보드 위치 분리]
# generate_signal_files.py(그리고 이걸 실행하는 contract_manager_server.py
# 등)는 C:\dashboard가 아닌 다른 폴더에 따로 보관하며 쓸 수도 있습니다.
# 다만 신호검색 파일들이 실제로 기록할 로그 폴더(data\...)는 예스스팟
# 대시보드/브릿지가 실제로 감시하는 위치(C:\dashboard)에 만들어져야
# 합니다 - 이 둘이 다른 폴더일 수 있으므로 명시적으로 분리했습니다.
#
# DASHBOARD_ROOT: 실제 dashboard_server.py/bridge_signals.py가 있는 위치.
#   여기 값을 실제 환경에 맞게 바꾸면, 이 생성기를 어느 폴더에 두고
#   실행하든 항상 정확한 곳에 data\ 폴더를 만들고, 생성되는 signal_*.js
#   파일들의 OUTPUT_FILE도 이 경로를 정확히 가리키게 됩니다.
DASHBOARD_ROOT = r"C:\dashboard_txt"  # [텍스트버전] 엑셀버전(C:\dashboard)과 데이터 폴더가 섞이지 않게 분리

# [2026-07-19 수정] 처음엔 config/contracts.json(하위폴더)을 찾도록
# 돼있었는데, 월물 관리 웹서버(contract_manager_server.py)는 사용성을
# 위해 "폴더 하나에 다 넣고 쓰는" 평평한 구조로 배포합니다 - 그 구조와
# 경로를 통일해서, contracts.json을 이 스크립트와 같은 폴더에서 찾습니다.
# (이건 생성기 자신의 설정파일이라 BASE_DIR 기준 그대로 - DASHBOARD_ROOT와
# 무관하게, 생성기를 어디 두든 항상 "생성기 옆"에서 contracts.json을 찾습니다.)
CONFIG_PATH = os.path.join(BASE_DIR, "contracts.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "generated")
# [2026-07-19 수정] DATA_DIR은 이제 BASE_DIR이 아니라 DASHBOARD_ROOT
# 기준입니다 - 실제 예스스팟이 쓰는 위치에 폴더를 만들어야 하기 때문에,
# 생성기 자신의 위치와는 분리했습니다.
DATA_DIR = os.path.join(DASHBOARD_ROOT, "data")

TICK_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "TICK_TEMPLATE.js")
MIN_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "MIN_TEMPLATE.js")

# [2026-09-01 전면개정][예스스팟 스크립트 v1.10과 재동기화] 예전엔 OUTPUT_FILE/
# DIAGNOSTIC_OUTPUT_FILE/PROGRESS_KEY/PENDING_STATE_KEY 전부를 파이썬이 각각
# 하드코딩된 "원본 리터럴 문자열"을 찾아서 개별적으로 치환해야 했다(구조
# 자체가 바뀌면 이 리터럴들이 전부 어긋나 조용히 깨지거나 assert로 막혔음
# - 실제로 예스스팟 스크립트가 그동안 여러 차례 리팩터링되면서 이 문제가
# 발생했다). 지금(v1.10) 예스스팟 스크립트는 그 파생값들을 전부 스크립트
# 자신이 실행시점에 MARKET_DATA_CODE/INSTRUMENT_NAME 두 값만으로 계산한다
# (스크립트 14행 주석: "[이식성] MARKET_DATA_CODE/INSTRUMENT_NAME 2개만
# 바꾸면 종목전환"). 그래서 이 생성기도 이제 그 두 값만 정확히 치환하면
# 되고, OUTPUT_FILE/DIAGNOSTIC_OUTPUT_FILE/PROGRESS_KEY/PENDING_STATE_KEY용
# 개별 치환 함수(예전의 apply_output_file/apply_diagnostic_file/
# apply_key_suffix/substitute)는 전부 필요 없어져 제거했다 - 스크립트
# 자신의 파생 계산 로직과 이중으로 유지보수할 필요가 사라짐(단일 진실원).
TICK_TEMPLATE_ORIGINAL = {"code": "NQU26", "name_en": "NASDAQ100"}
MIN_TEMPLATE_ORIGINAL = {"code": "GCQ26", "name_en": "GOLD"}

MARKET_DATA_CODE_RE = re.compile(r'var MARKET_DATA_CODE = "[^"]*";.*\n')
INSTRUMENT_NAME_RE = re.compile(r'var INSTRUMENT_NAME = "[^"]*";.*\n')


def apply_market_data_code(content, new_code):
    # [수정] 값만 바꾸고 주석은 템플릿 원본 그대로 남기면(예: GOLD 파일인데
    # 주석엔 "CME NASDAQ100..." 그대로) 사람이 읽을 때 헷갈리는 잘못된
    # 정보가 남는다(실제 발견된 문제) - 줄 전체를 새로 만들어 통째로
    # 교체해서 값/주석이 항상 같이 맞도록 한다.
    new_line = 'var MARKET_DATA_CODE = "%s"; // [생성기가 채움] 실제 예스스팟 코드로 반드시 확인 후 필요시 교체\n' % new_code
    new_content, n = MARKET_DATA_CODE_RE.subn(new_line, content, count=1)
    assert n == 1, "템플릿에서 MARKET_DATA_CODE 선언 줄을 못 찾음 - 템플릿이 바뀌었는지 확인 필요"
    return new_content


def apply_instrument_name(content, new_name):
    new_line = 'var INSTRUMENT_NAME = "%s"; // 신호파일에 찍히는 종목 표기(itemName)\n' % new_name
    new_content, n = INSTRUMENT_NAME_RE.subn(new_line, content, count=1)
    assert n == 1, "템플릿에서 INSTRUMENT_NAME 선언 줄을 못 찾음 - 템플릿이 바뀌었는지 확인 필요"
    return new_content


def verify_template_baseline(content, orig, template_name):
    """[안전장치] 실제로 치환하기 전에, 이 템플릿이 예상한 종목 기준(예:
    TICK_TEMPLATE.js는 나스닥100/NQU26)으로 시작하는 게 맞는지 확인한다.
    템플릿 파일이 실수로 뒤바뀌거나(예: TICK/MIN 자리 착각) 다른 종목
    기준으로 잘못 저장돼도, 조용히 엉뚱한 종목 이름이 섞인 파일을 만들어
    내는 대신 여기서 바로 명확한 에러로 멈춘다."""
    assert ('var MARKET_DATA_CODE = "' + orig["code"] + '"') in content, \
        "%s: 예상 기준코드(%s)와 실제 템플릿 안 MARKET_DATA_CODE가 다름 - 템플릿이 뒤바뀌었는지 확인 필요" % (template_name, orig["code"])
    assert ('var INSTRUMENT_NAME = "' + orig["name_en"] + '"') in content, \
        "%s: 예상 기준종목(%s)과 실제 템플릿 안 INSTRUMENT_NAME이 다름 - 템플릿이 뒤바뀌었는지 확인 필요" % (template_name, orig["name_en"])


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_template(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def month_suffix(contract):
    """monthLabel(예: "9월물", "12월물")에서 숫자만 뽑아 "(09)", "(12)" 같은
    파일명용 접미사를 만듭니다. 숫자를 못 찾으면(형식이 특이한 경우)
    빈 문자열을 돌려줘서 파일명 생성 자체는 절대 실패하지 않게 합니다.
    [2026-07-19 신규] 사용자 요청 - "U26"만 봐서는 몇 월인지 바로 안
    와닿아서, 파일명만 보고도 구분되게 월 숫자를 괄호로 덧붙입니다."""
    m = re.search(r"(\d+)", contract.get("monthLabel", ""))
    if not m:
        return ""
    return "(%02d)" % int(m.group(1))


def month_prefix(contract):
    """[2026-07-19 신규] 파일명 맨 앞에 "09_", "12_" 같은 월 접두사를
    붙입니다. 파일 탐색기에서 이름순 정렬하면 같은 월물끼리 자연스럽게
    묶여 보이게 하기 위함입니다(종목명 알파벳순이 아니라 월 순서로
    묶고 싶다는 사용자 요청). month_suffix와 숫자 추출 방식은 동일하되,
    괄호 없이 맨 앞에 붙는 형태(뒤에 밑줄)로 따로 둡니다."""
    m = re.search(r"(\d+)", contract.get("monthLabel", ""))
    if not m:
        return ""
    return "%02d_" % int(m.group(1))


def gen_min_file(instrument_slug, inst_cfg):
    """[2026-08-30 수정][다음월물 전용화] 활성 월물은 이미 실시간으로
    운영 중인 파일을 이 도구로 다시 만들어 덮어쓸 이유가 없다는 지적에
    따라, 이 생성기는 이제 next(다음월물)만 만든다 - contract_key
    분기 자체를 없애서 "활성 파일이 실수로 다시 만들어질 가능성"을
    구조적으로 차단한다."""
    contract = inst_cfg["next"]
    content = load_template(MIN_TEMPLATE_PATH)
    verify_template_baseline(content, MIN_TEMPLATE_ORIGINAL, "MIN_TEMPLATE.js")
    content = apply_market_data_code(content, contract["code"])
    content = apply_instrument_name(content, inst_cfg["nameEnDefault"])

    header = build_header_banner(inst_cfg, contract, "next", "min")
    content = header + content

    filename = "%ssignal_%s_min_%s%s.js" % (month_prefix(contract), instrument_slug, contract["label"], month_suffix(contract))
    return filename, content


def gen_tick_file(instrument_slug, inst_cfg):
    """[2026-08-30 수정][다음월물 전용화] gen_min_file과 동일한 이유로
    next만 생성한다."""
    contract = inst_cfg["next"]
    content = load_template(TICK_TEMPLATE_PATH)
    verify_template_baseline(content, TICK_TEMPLATE_ORIGINAL, "TICK_TEMPLATE.js")
    content = apply_market_data_code(content, contract["code"])
    content = apply_instrument_name(content, inst_cfg["nameEnDefault"])

    header = build_header_banner(inst_cfg, contract, "next", "tick")
    content = header + content

    filename = "%ssignal_%s_tick_%s%s.js" % (month_prefix(contract), instrument_slug, contract["label"], month_suffix(contract))
    return filename, content


def build_header_banner(inst_cfg, contract, contract_key, kind):
    role = "다음 월물(사전 준비용)"
    kind_label = {"min": "분봉", "tick": "틱봉(하이브리드 실시간)"}[kind]
    return (
        "// ================================================================================\n"
        "// [자동생성됨] generate_signal_files.py + config/contracts.json 로 생성된 파일입니다.\n"
        "//   이 파일을 직접 수정하지 마세요 - 다음 재생성 때 덮어써집니다.\n"
        "//   고칠 내용이 있으면 templates/ 안의 템플릿을 고치고 다시 생성하세요.\n"
        "// [종목] %s (%s) / [월물] %s %s (%s) - %s\n"
        "// [만기(마지막 거래일) 예정] %s - 반드시 실제 거래소/예스스팟 정보로 재확인 필요\n"
        "// [분류] %s\n"
        "// ================================================================================\n\n"
    ) % (
        inst_cfg["nameKr"], inst_cfg["nameEnDefault"],
        contract["code"], contract["monthLabel"], contract["label"], role,
        contract["lastTradingDay"], kind_label,
    )


def parse_slug_arg():
    """[2026-08-10 추가][종목별 개별생성] 커맨드라인에서 "--slug nasdaq"
    형태로 넘어오면 그 종목 하나만 생성합니다. 안 넘어오면(기존 그대로)
    전체 종목을 생성합니다 - 완전히 하위호환됩니다."""
    args = sys.argv[1:]
    if "--slug" in args:
        idx = args.index("--slug")
        if idx + 1 < len(args):
            return args[idx + 1]
    return None


def main():
    config = load_config()
    target_slug = parse_slug_arg()
    if target_slug is not None and target_slug not in config["instruments"]:
        raise SystemExit("!! 알 수 없는 종목 슬러그: %s (가능한 값: %s)" % (
            target_slug, ", ".join(config["instruments"].keys())))

    # [2026-07-19 신규][로그파일 분리] 종목별 로그 디렉토리를 미리 만들어
    # 둡니다(DASHBOARD_ROOT\data\nasdaq, ...\sp500, ...\gold). 이 생성기
    # 자신은 어느 폴더에 두고 실행하든 상관없습니다 - DATA_DIR이
    # DASHBOARD_ROOT 기준으로 계산되므로, 항상 실제 대시보드/브릿지가
    # 감시하는 정확한 위치에 폴더가 생깁니다(파일 맨 위 DASHBOARD_ROOT
    # 값만 실제 환경에 맞게 설정돼 있으면 됩니다).
    # [주의] Main.PrintOnFile 같은 파일쓰기 API는 보통 폴더가 없으면
    # 그냥 실패하지, 알아서 폴더를 만들어주지 않습니다 - 그래서 반드시
    # 예스스팟이 실행되기 전에 이 폴더들이 미리 존재해야 합니다.
    os.makedirs(DATA_DIR, exist_ok=True)
    slugs_to_process = [target_slug] if target_slug is not None else list(config["instruments"].keys())
    for slug in slugs_to_process:
        os.makedirs(os.path.join(DATA_DIR, slug), exist_ok=True)

    # [2026-07-19 신규] 재생성 전에 이전 산출물을 깨끗이 비웁니다. 설정이
    # 바뀌면(예: 다음 월물 라벨이 Z26 -> H27로 바뀌는 경우) 예전 파일이
    # 새 파일과 같이 남아서 "지금 뭐가 최신인지" 헷갈리는 걸 막기 위함
    # 입니다. 이 폴더 안 파일은 전부 이 스크립트가 만든 것뿐이라(사람이
    # 직접 편집한 게 하나도 없다는 전제 - 각 파일 상단 배너에도 "직접
    # 수정하지 마세요"라고 명시돼 있음) 통째로 지워도 안전합니다.
    # [2026-08-10 수정][종목별 개별생성] target_slug가 지정된 경우엔
    # 그 종목의 파일("signal_{slug}_"가 들어간 파일)만 지웁니다 - 다른
    # 종목이 이미 만들어둔 최신 파일을 실수로 건드리지 않기 위함입니다.
    # 지정이 없으면(기존과 동일) 전체를 비웁니다.
    if os.path.isdir(OUTPUT_DIR):
        slug_marker = ("signal_%s_" % target_slug) if target_slug is not None else None
        for f in os.listdir(OUTPUT_DIR):
            if not f.endswith(".js"):
                continue
            if slug_marker is not None and slug_marker not in f:
                continue
            os.remove(os.path.join(OUTPUT_DIR, f))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generated = []
    for slug in slugs_to_process:
        inst_cfg = config["instruments"][slug]
        # [2026-08-30 수정][다음월물 전용화] 활성 월물은 이미 실시간으로
        # 운영 중인 파일을 이 도구가 또 만들어 덮어쓸 이유가 없다는
        # 지적에 따라 next만 생성한다(active 분기/워밍업 전용 파일 생성
        # 자체를 제거함 - "실수로 활성 파일이 재생성될 가능성"을 코드
        # 구조적으로 차단).
        if not inst_cfg.get("next"):
            print("!! [건너뜀] %s: next(다음월물) 설정이 없습니다." % slug)
            continue

        fname, content = gen_min_file(slug, inst_cfg)
        _write(fname, content)
        generated.append(fname)

        fname, content = gen_tick_file(slug, inst_cfg)
        _write(fname, content)
        generated.append(fname)

    scope_note = ("%s 종목만" % target_slug) if target_slug is not None else "전체 종목"
    print("\n%s 총 %d개 파일 생성 완료 (%s)" % (scope_note, len(generated), OUTPUT_DIR))
    for f in sorted(generated):
        print("  -", f)


def _write(filename, content):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
