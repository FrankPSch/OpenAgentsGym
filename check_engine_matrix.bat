@echo off
REM Preconditions for run_engine_matrix.bat. Runs nothing, spends nothing.
REM Every line that says FAIL is a reason the matrix would abort.
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "BAD=0"

echo === binaries ===
set "OCBIN="
for /f "usebackq delims=" %%R in (`py -3 "%~dp0engine_find_opencode.py"`) do set "OCBIN=%%R"
if not defined OCBIN set "OCBIN=NONE"
if "%OCBIN%"=="NONE" (
  echo   FAIL no launchable opencode.exe found
  echo        APPDATA here is: %APPDATA%
  echo        ^(if that is not your profile, this window is elevated^)
  set "BAD=1"
) else (
  echo   OK   opencode.exe in %OCBIN%
  set "PATH=%OCBIN%;%PATH%"
)
for /f "delims=" %%R in ('py -3 -c "import shutil;print(shutil.which('opencode') or 'NONE')"') do set "OC=%%R"
if "!OC!"=="NONE" (echo   FAIL shutil.which cannot see opencode & set "BAD=1") else (echo   OK   which -^> !OC!)
for /f "delims=" %%R in ('py -3 -c "import shutil;print(shutil.which('claude') or 'NONE')"') do set "CL=%%R"
if "!CL!"=="NONE" (echo   WARN claude not found - the /billed leg would abort) else (echo   OK   claude -^> !CL!)
for /f "delims=" %%R in ('py -3 -c "import shutil;print(shutil.which('codex') or 'NONE')"') do set "CX=%%R"
if "!CX!"=="NONE" (echo   note codex not installed - gpt_02 aborts with exit 6, as expected) else (echo   OK   codex -^> !CX!)

echo === interpreter the projects pin ===
py -3.10 -c "import sys;print('   OK   python',sys.version.split()[0])" 2>nul || (echo   FAIL py -3.10 missing - every run exits 3 & set "BAD=1")

echo === services ===
py -3 -c "import urllib.request,json;u=urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=8);print('   OK   ollama',json.load(u)['version'])" 2>nul || (echo   FAIL ollama not answering on 11434 & set "BAD=1")
py -3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:4000/health/liveliness',timeout=8);print('   OK   litellm on 4000')" 2>nul || (echo   FAIL litellm not answering on 4000 & set "BAD=1")

echo === models the configs name ===
py -3 "%~dp0engine_check_models.py" || set "BAD=1"

echo === opencode provider config ===
if exist "%USERPROFILE%\.config\opencode\opencode.jsonc" (echo   OK   opencode.jsonc) else if exist "%USERPROFILE%\.config\opencode\opencode.json" (echo   OK   opencode.json) else (echo   FAIL no user-level opencode config - provider 'litellm' will not resolve & set "BAD=1")

echo === configs ===
for %%C in (opencode_01 opencode_02 opencode_03 model_02 gpt_02) do (
  if exist ".llm_config.%%C" (echo   OK   .llm_config.%%C) else (echo   FAIL .llm_config.%%C missing & set "BAD=1")
)

echo === free RAM ===
REM qwen3-coder-30b is 18 GB of weights. Below ~20 GB free it will spill to CPU
REM or fail to load - that is what OOM'd it on an earlier attempt.
for /f "tokens=2 delims==" %%M in ('wmic OS get FreePhysicalMemory /value 2^>nul ^| findstr "="') do set /a FREEGB=%%M/1048576
echo   %FREEGB% GB free

echo.
if "%BAD%"=="1" (
  echo RESULT: NOT READY - fix the FAIL lines above.
  echo.
  pause
  exit /b 1
) else (
  echo RESULT: READY
  echo   run_engine_matrix.bat           local only, free
  echo   run_engine_matrix.bat /billed   adds claude-sonnet-5 ^(~$0.08^)
  echo.
  pause
  exit /b 0
)
