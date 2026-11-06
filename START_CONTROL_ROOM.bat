@echo off
setlocal
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Python was not found on PATH. Install Python 3.10+ from python.org and tick "Add to PATH". & pause & exit /b 1)
python -c "import pandas, pyarrow, yaml, pydantic, requests, dotenv, sklearn, matplotlib, tzdata" >nul 2>&1 || (
  echo Installing Python packages ^(first run only^)...
  python -m pip install --quiet pandas numpy scipy scikit-learn pyarrow requests "pydantic>=2" pyyaml python-dotenv openpyxl tzdata matplotlib anthropic
)
title RockWatch control room - http://localhost:8600
echo Starting the RockWatch control room on http://localhost:8600  (close this window to stop)
start "" cmd /c "timeout /t 3 /nobreak >nul & start chrome http://localhost:8600/ || start http://localhost:8600/"
python -m rockwatch ui --port 8600
pause
