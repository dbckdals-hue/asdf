@echo off
REM ================================================================================
REM PROJECT OVERVIEW - for a fresh chat/session that only has this file
REM
REM Purpose: Launches the two Python servers needed for the YesSpot signal
REM dashboard, then opens the dashboard in the default browser.
REM
REM Full system:
REM   [6 YesSpot strategy scripts - signal_nasdaq_min.js etc, run inside YesTrader]
REM     -> write signals via Main.PrintOnFile
REM     -> [yesspot_signals.txt]
REM        -> [bridge_signals_txt.py] watches file, forwards via WebSocket (port 9101)
REM           -> [dashboard_server_txt.py] serves the html on port 8081
REM              -> [yesspot_signals_dashboard_txt.html] shows the live signal list
REM
REM Required files - all must be in this same folder:
REM   bridge_signals_txt.py
REM   dashboard_server_txt.py
REM   yesspot_signals_dashboard_txt.html
REM   (yesspot_signals.txt gets created automatically once a signal is found)
REM
REM Usage: just double-click this .bat file. No admin rights needed.
REM To stop everything: click "Dashboard shutdown" button inside the dashboard page,
REM or just close the two console windows manually.
REM ================================================================================

title YesSpot Signal Dashboard Launcher (TEXT version)

cd /d "%~dp0"
echo Current folder: %cd%
echo.

echo [1/3] Starting bridge_signals_txt.py in a new window...
start "Bridge Signals - closes automatically" cmd /c python bridge_signals_txt.py

echo [2/3] Starting local web server for the dashboard on port 8081...
start "Dashboard Web Server - closes automatically" cmd /c python dashboard_server_txt.py

echo [3/3] Waiting 2 seconds, then opening the dashboard...
timeout /t 2 /nobreak >nul
start "" "http://localhost:8081/yesspot_signals_dashboard_txt.html"

echo.
echo Done. You can close this window now.
echo Keep the two other windows open while you use the dashboard.
timeout /t 5
