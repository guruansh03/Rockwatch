@echo off
setlocal
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Python was not found on PATH. Install Python 3.10+ from python.org and tick "Add to PATH". & pause & exit /b 1)
python -c "import pandas, pyarrow, yaml, pydantic, requests, dotenv, sklearn, matplotlib, tzdata" >nul 2>&1 || (
  echo Installing Python packages ^(first run only^)...
  python -m pip install --quiet pandas numpy scipy scikit-learn pyarrow requests "pydantic>=2" pyyaml python-dotenv openpyxl tzdata matplotlib anthropic
)
title RockWatch live demo - http://localhost:8600
set SCENARIO=%1
if "%SCENARIO%"=="" set SCENARIO=dev_val_Y
echo Starting 16 agent processes + replay (%SCENARIO%) + control room on http://localhost:8600
echo Scenarios: dev_val_Y (default) ^| dev_val (Alaska) ^| after the final eval: storm_A quiet_A quake_A storm_Y quiet_Y quake_Y
echo The browser opens once the agents are up. Space = pause/resume. Close this window to stop.
start "" cmd /c "timeout /t 14 /nobreak >nul & start chrome http://localhost:8600/ || start http://localhost:8600/"
python -m rockwatch run-demo --scenario %SCENARIO% --llm on --speed 1.5 --no-browser
pause
