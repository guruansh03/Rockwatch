@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title RockWatch - Alaska data pipeline
python --version >nul 2>&1 || (echo Python was not found on PATH. & pause & exit /b 1)
echo ============================================================================
echo  Alaska (Region A): finish weather, rebuild features, retrain, validate
echo  Open-Meteo free quota: about 5,000 weighted calls/hour, 10,000/day.
echo  Each zone costs ~270, so this pauses for the hourly limit and resumes.
echo  Safe to close and re-run: the fetch is resumable, nothing is re-downloaded.
echo ============================================================================

:fetch
python -m rockwatch fetch-weather --regions A
set RC=%errorlevel%
if "%RC%"=="0" goto build
if "%RC%"=="10" (
  echo.
  echo [%time%] Quota pause - waiting 20 minutes, then resuming. Close this window to stop.
  timeout /t 1200 /nobreak >nul
  goto fetch
)
echo fetch-weather failed with code %RC%. See data\cache\weather\fetch_log.jsonl
pause & exit /b %RC%

:build
echo.
echo [1/4] build-data (features + labels + splits)
python -m rockwatch build-data --regions A || (echo build-data failed & pause & exit /b 1)
echo [2/4] train (fusion model + ablations, thresholds on validation, t2 rule from config)
python -m rockwatch train --regions A || (echo train failed & pause & exit /b 1)
echo [3/4] eval on VALIDATION only (test stays sealed)
python -m rockwatch eval --split val --regions A || (echo eval failed & pause & exit /b 1)
echo [4/4] CP2 packet for Alaska
python -m rockwatch cp2-packet --region A || (echo cp2-packet failed & pause & exit /b 1)
echo.
echo Done. Alaska data complete. Next:
echo   START_LIVE_DEMO.bat dev_val      - live replay of Alaska (validation period)
echo   FINAL_TEST_EVAL.bat              - one-time sealed test evaluation (CP2 approved)
pause
