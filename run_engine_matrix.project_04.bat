@echo off
REM ===========================================================================
REM Engine bring-up matrix: 04_python_xlarge x 00_empty across engines/models.
REM
REM   opencode_01  litellm/gpt-oss-20b      (proven: scored 0.894 on 2026-09-11)
REM   opencode_02  litellm/qwen3-4b         (stalled >10 min previously)
REM   opencode_03  litellm/qwen3-coder-30b  (OOM'd on Vulkan previously)
REM   model_02     claude-sonnet-5          (BILLED - opt in with /billed)
REM   gpt_02       gpt-5-codex              (codex not installed - expect exit 6)
REM
REM A bring-up, not a campaign: one repeat, one project, the no-methodology
REM anchor. It cannot rank anything (chapter 17 wants >=3 repeats).
REM
REM USAGE
REM   run_engine_matrix.bat           local engines only, costs nothing
REM   run_engine_matrix.bat /billed   also runs claude-sonnet-5 against Anthropic
REM
REM The claude leg is OPT-IN because the first version of this file ran it even
REM after all three local legs had already failed, which spent money to confirm
REM a path the differential tests had already verified.
REM
REM TIME: the proven leg took 9m40s. The two unproven local legs are bounded
REM only by CLI_TIMEOUT_S (3600 s each) - cfg_bound is walltime on this engine -
REM so worst case is ~2h of waiting for stalls.
REM
REM A failing leg is a RESULT: the batch continues and reports every exit code.
REM   3 = interpreter missing   4 = config rejected   6 = binary missing
REM ===========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "BILLED=0"
if /i "%~1"=="/billed" set "BILLED=1"

REM --- opencode binary -------------------------------------------------------
REM npm installs a .cmd shim CreateProcess cannot launch, and resolve_cli()
REM correctly refuses it. The real binary sits under node_modules.
REM %APPDATA% is NOT stable across the ways a .bat is started - an elevated
REM console resolves it to another profile, where the package is not installed.
REM Testing one literal path therefore reported "not installed" on a machine
REM where it was installed. engine_find_opencode.py probes several locations instead.
where py >nul 2>&1
if errorlevel 1 (
  echo FATAL: the `py` launcher is not on PATH in this window, so nothing can run.
  echo        A double-clicked window inherits a different PATH than a terminal
  echo        started from your profile. Try running this from a terminal.
  echo.
  pause
  exit /b 9
)
set "OCBIN="
for /f "usebackq delims=" %%R in (`py -3 "%~dp0engine_find_opencode.py"`) do set "OCBIN=%%R"
if not defined OCBIN set "OCBIN=NONE"
if "%OCBIN%"=="NONE" (
  echo FATAL: no launchable opencode.exe found in any known location.
  echo        APPDATA is currently: %APPDATA%
  echo        If that is not your own profile, this window is elevated and is
  echo        looking in the wrong place - run it without administrator rights.
  echo        Otherwise install with:
  echo          npm install -g --allow-scripts=opencode-ai opencode-ai
  echo.
  pause
  exit /b 9
)
set "PATH=%OCBIN%;%PATH%"

REM --- prove the harness can resolve it BEFORE any leg runs ------------------
REM This is the check whose absence cost a billed run: three legs aborted with
REM exit 6 and the batch walked straight into the paid one.
REM `py` itself must be reachable, or the for/f below yields nothing and OCRES
REM stays undefined - which would pass the guard while every leg then fails.
where py >nul 2>&1
if errorlevel 1 (
  echo FATAL: the `py` launcher is not on PATH in this window.
  echo        Nothing can run. This is the most likely reason a double-clicked
  echo        window closes instantly: Explorer launches with a different PATH
  echo        than a terminal started from your profile.
  echo.
  pause
  exit /b 9
)

set "OCRES="
for /f "delims=" %%R in ('py -3 -c "import shutil;print(shutil.which('opencode') or 'NONE')"') do set "OCRES=%%R"
if not defined OCRES (
  echo FATAL: could not run `py -3` to resolve opencode. Nothing has been run.
  echo.
  pause
  exit /b 9
)
if "!OCRES!"=="NONE" (
  echo FATAL: python's shutil.which cannot see opencode even with
  echo        %OCBIN%
  echo        prepended to PATH. run_master.py would abort every opencode leg
  echo        with exit 6. Nothing has been run and nothing has been spent.
  echo.
  echo PATH begins: !PATH:~0,200!
  echo.
  pause
  exit /b 9
)
echo opencode resolves to: !OCRES!

set "LOGDIR=local\engine_matrix"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "STAMP=%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%"
set "STAMP=%STAMP: =0%"
set "SUMMARY=%LOGDIR%\summary_%STAMP%.txt"

echo engine matrix %STAMP% > "%SUMMARY%"
echo project=04_python_xlarge methodology=00_empty >> "%SUMMARY%"
echo opencode=!OCRES! >> "%SUMMARY%"
echo. >> "%SUMMARY%"

call :leg opencode_01 "gpt-oss-20b     local  proven"
call :leg opencode_02 "qwen3-4b        local  unproven"
call :leg opencode_03 "qwen3-coder-30b local  unproven"

if "%BILLED%"=="1" (
  call :leg model_02 "claude-sonnet-5 cloud  BILLED"
) else (
  echo.
  echo ==== model_02 SKIPPED ^(billed^) - pass /billed to include it ====
  echo model_02  skipped  ^(billed, not requested^) >> "%SUMMARY%"
)

call :leg gpt_02 "gpt-5-codex     cloud  codex not installed"

echo.
echo ============ SUMMARY ============
type "%SUMMARY%"
echo.
echo Logs: %LOGDIR%\
echo.
REM Every other batch that runs a SET of pairs merges its rows itself -- the
REM --matrix entry points call consolidate() internally, and the smoke/turbo/
REM selected batches call rebuild_results_table.bat. This one printed a
REM reminder instead, so a finished matrix left its rows in run directories
REM and the published table unchanged until someone noticed.
call "%~dp0rebuild_results_table.bat"
echo.
pause
exit /b 0

:leg
set "CFG=%~1"
echo.
echo ==== %CFG%  (%~2) ====

REM Evict whatever is resident before starting. Ollama holds a model for ~5 min
REM after use, so leg N+1 would otherwise start while leg N's weights are still
REM in memory. On 2026-09-11 that made gpt-oss-20b run 2.6x slower and produce
REM zero edits, then killed the 30B with APIError.
for /f "usebackq tokens=2 delims==" %%M in (`findstr /b "MODEL=" ".llm_config.%CFG%"`) do set "LEGMODEL=%%M"
if defined LEGMODEL (
  echo   unloading previous model...
  py -3 "%~dp0engine_leg.py" unload "!LEGMODEL!"
)

echo start %TIME%
py -3 run_master.py 04_python_xlarge 00_empty --config .llm_config.%CFG% > "%LOGDIR%\%CFG%_%STAMP%.log" 2>&1
set "RC=!ERRORLEVEL!"
echo end   %TIME%  exit=!RC!

REM run_master exits 0 for any run that reached a row - including one that says
REM APIError and scores 0.0000. The exit code alone is not a pass signal, so
REM judge the row itself.
set "VERD=n/a"
if "!RC!"=="0" (
  py -3 "%~dp0engine_leg.py" verdict %CFG%
  if errorlevel 1 (set "VERD=FAIL") else (set "VERD=PASS")
) else (
  echo   --- last lines of log ---
  powershell -NoProfile -Command "Get-Content '%LOGDIR%\%CFG%_%STAMP%.log' -Tail 3 | ForEach-Object { '   ' + $_ }"
  set "VERD=ABORT"
)
echo %CFG%  exit=!RC!  !VERD!  (%~2) >> "%SUMMARY%"
exit /b 0
