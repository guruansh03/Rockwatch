@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title RockWatch - FINAL test evaluation (one time)
python --version >nul 2>&1 || (echo Python was not found on PATH. & pause & exit /b 1)
echo ============================================================================
echo  FINAL TEST EVALUATION - regions A and Y - runs ONCE (CP2 approved)
echo  A re-run is refused unless given a reason, and every run is logged in
echo  reports\final_runs.log. Validation numbers are not touched.
echo ============================================================================
echo.
set LLM=off
set PROV=none
for /f "usebackq delims=" %%p in (`python -c "from dotenv import dotenv_values as d; v=d('.env'); g=(v.get('GROQ_API_KEY') or '').strip(); a=(v.get('ANTHROPIC_API_KEY') or '').strip(); print('groq' if g else 'anthropic' if a else 'none')"`) do set PROV=%%p
if not "!PROV!"=="none" (
  echo LLM provider: !PROV! ^(key found in .env^) - running the real-LLM smoke test first...
  set ROCKWATCH_LLM_PROVIDER=!PROV!
  python -m rockwatch llm-smoke --provider !PROV! --n 3
  if errorlevel 1 (
    echo.
    echo LLM smoke test FAILED - fix the key / model IDs in .env before the final run.
    pause & exit /b 1
  )
  set LLM=on
) else (
  echo No GROQ_API_KEY or ANTHROPIC_API_KEY in .env.
  echo   [1] Run the final now WITHOUT the LLM verifier ^(the "with LLM" column will be absent;
  echo       adding it later needs a logged re-run with a reason^)
  echo   [2] Stop - I will add a key to .env first
  choice /c 12 /n /m "Choose 1 or 2: "
  if errorlevel 2 exit /b 0
)
echo.
echo Running: eval --split test --final --regions A Y --llm !LLM!
echo ^(with Groq free tier: paced to the rate limit, about 25 minutes^)
python -m rockwatch eval --split test --final --regions A Y --llm !LLM!
if errorlevel 1 (echo Final evaluation refused or failed - read the message above. & pause & exit /b 1)
echo.
echo Final reports written under reports\eval_*_test. Copy numbers verbatim from metrics.json / report.md.
pause
