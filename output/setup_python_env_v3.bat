@echo off
chcp 65001 >nul
title YesSpot 대시보드 환경 자동 설치 v3
REM ================================================================================
REM setup_python_env_v3.bat
REM
REM 역할: 새 컴퓨터에서 C:\dashboard 아래에 실행파일들만 복사하면 바로 돌아가도록 환경을 만든다.
REM   1) C:\dashboard 폴더 생성 (그 아래 data 폴더 등은 만들지 않음)
REM   2) 파이썬 확인 - 없으면 winget으로 설치(설치 후 같은 창에서 이어서 진행)
REM   3) websockets + tzdata 설치
REM      (tzdata가 없으면 윈도우 파이썬은 시카고/서울 시간대를 몰라서 시간 변환이 틀어진다)
REM   4) 설치 확인(websockets 불러오기, 시카고/서울 시간대 확인)
REM
REM 필요조건: 인터넷 연결 / 파이썬이 없을 때는 winget(Windows 10 최신 빌드, Windows 11 기본 포함)
REM 이 파일이 하지 않는 것: bridge_signals.py 등 파일 복사, YesSpot/Excel 설치
REM ================================================================================

set "PYEXE="
set "PYARG="

echo [1/4] 폴더 생성 중...
if not exist "C:\dashboard" mkdir "C:\dashboard"
if not exist "C:\dashboard" goto FOLDER_FAIL
echo C:\dashboard 폴더 준비 완료.
echo.

echo [2/4] 파이썬 확인 중...
python --version >nul 2>nul
if not errorlevel 1 set "PYEXE=python"
if defined PYEXE goto PY_FOUND
py -3 --version >nul 2>nul
if not errorlevel 1 set "PYEXE=py"
if not errorlevel 1 set "PYARG=-3"
if defined PYEXE goto PY_FOUND

echo 파이썬이 없어서 설치합니다. winget 확인 중...
where winget >nul 2>nul
if errorlevel 1 goto NO_WINGET
winget install --id Python.Python.3.13 -e --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto PY_INSTALL_FAIL
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set PYEXE="%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "%ProgramFiles%\Python313\python.exe" set PYEXE="%ProgramFiles%\Python313\python.exe"
if defined PYEXE goto PY_FOUND
echo.
echo 파이썬 설치는 끝났지만 설치 위치를 찾지 못했습니다.
echo 이 창을 닫고 새 cmd 창에서 이 파일을 다시 실행해주세요.
echo.
pause
exit /b 0

:PY_FOUND
%PYEXE% %PYARG% --version
echo.

echo [3/4] websockets, tzdata 패키지 설치 중...
%PYEXE% %PYARG% -m pip install --upgrade pip
%PYEXE% %PYARG% -m pip install websockets tzdata
if errorlevel 1 goto PIP_FAIL
echo.

echo [4/4] 설치 확인 중...
%PYEXE% %PYARG% -c "import websockets; from zoneinfo import ZoneInfo; ZoneInfo('America/Chicago'); ZoneInfo('Asia/Seoul'); print('websockets', websockets.__version__, '/ 시간대 확인 OK')"
if errorlevel 1 goto VERIFY_FAIL
echo.

echo ================================================================
echo 환경 준비가 끝났습니다.
echo  - 폴더: C:\dashboard
echo  - 파이썬 + websockets + tzdata
echo.
if exist "C:\dashboard\bridge_signals.py" (echo  - bridge_signals.py 확인됨) else (echo  - bridge_signals.py 는 아직 C:\dashboard 에 없습니다 - 실행파일들을 복사해주세요)
echo.
echo 이 창에서 파이썬을 새로 설치했다면, 새 cmd 창을 열어야 PATH가 반영됩니다.
echo ================================================================
pause
exit /b 0

:FOLDER_FAIL
echo.
echo [오류] C:\dashboard 폴더를 만들지 못했습니다. 관리자 권한으로 다시 실행해주세요.
echo.
pause
exit /b 1

:NO_WINGET
echo.
echo [오류] winget이 없습니다. Microsoft Store에서 앱 설치 관리자(App Installer)를 설치하거나,
echo https://www.python.org/downloads/ 에서 파이썬을 수동 설치 후 이 파일을 다시 실행해주세요.
echo 수동 설치 때는 Add python.exe to PATH 를 꼭 체크해주세요.
echo.
pause
exit /b 1

:PY_INSTALL_FAIL
echo.
echo [오류] winget으로 파이썬 설치에 실패했습니다.
echo https://www.python.org/downloads/ 에서 수동 설치 후 이 파일을 다시 실행해주세요.
echo 수동 설치 때는 Add python.exe to PATH 를 꼭 체크해주세요.
echo.
pause
exit /b 1

:PIP_FAIL
echo.
echo [오류] 패키지 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행해주세요.
echo.
pause
exit /b 1

:VERIFY_FAIL
echo.
echo [오류] 설치는 됐지만 확인에 실패했습니다. 위 메시지를 확인해주세요.
echo.
pause
exit /b 1
