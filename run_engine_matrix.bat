@echo off
REM ===========================================================================
REM Engine bring-up matrix: one [project] x [methodology] pair across engines.
REM
REM USAGE
REM   run_engine_matrix.bat                       defaults below, local only
REM   run_engine_matrix.bat p03_python_large       other project, same methodology
REM   run_engine_matrix.bat p03_python_large 29_x  both named
REM   run_engine_matrix.bat /billed               also runs the two cloud legs
REM
REM The project and the methodology are parameters, not edits. Editing a .bat
REM that is running corrupts it: cmd re-reads the file at a stored byte offset,
REM so a file that changed length resumes mid-line. Pass an argument instead.
REM
REM A bring-up, not a campaign: one repeat, one project, one methodology. It
REM cannot rank anything - chapter 17 wants >=3 repeats before rows are poolable.
REM
REM The two cloud legs are OPT-IN together behind /billed. An earlier version
REM ran claude even after all three local legs had failed, spending money to
REM confirm a path the differential tests had already verified. They run FIRST
REM so the cheap, fast, known-good answer arrives before the long local waits.
REM
REM TIME: local legs are bounded only by CLI_TIMEOUT_S (3600 s each), so the
REM worst case for three of them is ~3h. A failing leg is a RESULT: the batch
REM carries on and reports every code.
REM ===========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- parameters ------------------------------------------------------------
set "PROJECT=p01_python_small"
set "METHODOLOGY=m00_empty"
set "BILLED=1"

set "POS=0"
:parseargs
if "%~1"=="" goto parsed
if /i "%~1"=="/billed" (
  set "BILLED=1"
) else (
  set /a POS+=1
  if "!POS!"=="1" set "PROJECT=%~1"
  if "!POS!"=="2" set "METHODOLOGY=%~1"
)
shift
goto parseargs
:parsed

REM --- resolve everything the preflight branches on --------------------------
REM Four separate FATAL blocks used to repeat the same environment story. They
REM all branch on the same four values, so the values are printed once here and
REM the failure text lives in one place (:fatal).
set "HASPY=no"
where py >nul 2>&1
if not errorlevel 1 set "HASPY=yes"

set "OCBIN=NONE"
set "OCRES=NONE"
if "!HASPY!"=="yes" (
  REM npm installs a .cmd shim CreateProcess cannot launch, and resolve_cli()
  REM correctly refuses it. The real binary sits under node_modules. APPDATA is
  REM not stable across the ways a .bat is started - an elevated console
  REM resolves it to another profile - so a literal path is not probed.
  for /f "usebackq delims=" %%R in (`py -3 "%~dp0engine_find_opencode.py"`) do set "OCBIN=%%R"
  if not "!OCBIN!"=="NONE" set "PATH=!OCBIN!;!PATH!"
  for /f "delims=" %%R in ('py -3 -c "import shutil;print(shutil.which('opencode') or 'NONE')"') do set "OCRES=%%R"
  if not defined OCRES set "OCRES=NONE"
)

echo ============ RUN ============
echo   project      = !PROJECT!
echo   methodology  = !METHODOLOGY!
echo   billed legs  = !BILLED!   ^(1 = claude and gpt included^)
echo ---------- ENVIRONMENT ----------
echo   py on PATH   = !HASPY!
echo   APPDATA      = %APPDATA%
echo   opencode dir = !OCBIN!
echo   which^(opencode^) = !OCRES!
echo =================================

if "!HASPY!"=="no" set "MSG=the py launcher is not on PATH in this window" & goto fatal
if "!OCBIN!"=="NONE" set "MSG=no launchable opencode.exe found in any known location" & goto fatal
if "!OCRES!"=="NONE" set "MSG=python cannot see opencode even with its directory prepended to PATH" & goto fatal
if not exist "projects\!PROJECT!" set "MSG=project !PROJECT! does not exist under projects\" & goto fatal
if not exist "methodology\!METHODOLOGY!" set "MSG=methodology !METHODOLOGY! does not exist under methodology\" & goto fatal

set "LOGDIR=local\engine_matrix"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "STAMP=%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%"
set "STAMP=%STAMP: =0%"
set "SUMMARY=%LOGDIR%\summary_%STAMP%.txt"

echo engine matrix %STAMP% > "%SUMMARY%"
echo project=!PROJECT! methodology=!METHODOLOGY! >> "%SUMMARY%"
echo opencode=!OCRES! >> "%SUMMARY%"
echo. >> "%SUMMARY%"

REM --- cloud legs first ------------------------------------------------------
REM Both are billed, so both sit behind the same opt-in. Running them first
REM means the fast known-good reference lands before hours of local waiting.
if "!BILLED!"=="1" (
  call :leg e02_claude_sonnet_5 "claude-sonnet-5 cloud  BILLED"
  call :leg e05_gpt_5_codex   "gpt-5-codex     cloud  BILLED"
) else (
  echo.
  echo ==== e02_claude_sonnet_5 and e05_gpt_5_codex SKIPPED - pass /billed to include them ====
  echo e02_claude_sonnet_5  skipped  ^(billed, not requested^) >> "%SUMMARY%"
  echo e05_gpt_5_codex    skipped  ^(billed, not requested^) >> "%SUMMARY%"
)

REM --- local legs ------------------------------------------------------------
call :leg e06_local_gptoss_20b "gpt-oss-20b     local  free"
call :leg e07_local_qwen3_4b "qwen3-4b        local  free"
call :leg e08_local_qwen3coder_30b "qwen3-coder-30b local  free"

echo.
echo ============ SUMMARY ============
type "%SUMMARY%"
echo.
echo ---------- EXIT CODES ----------
echo   run_master.py, per leg:
echo     0  the run reached a row. NOT a pass - a row saying APIError and
echo        scoring 0.0000 also exits 0, which is why the verdict below is
echo        read from the row itself and not from this code.
echo     3  python interpreter missing (run_master needs 3.10)
echo     4  config rejected (a mandatory key blank or unknown in .llm_config)
echo     6  engine binary missing or unlaunchable (an npm .cmd shim counts)
echo.
echo   this batch:
echo     0  every leg was attempted and reported
echo     9  preflight refused to start: see the FATAL block, nothing was spent
echo.
echo   verdict, from engine_leg.py against the written row:
echo     PASS   scored above zero and verification passed
echo     FAIL   a row exists but it does not clear the bar
echo     ABORT  no row: the leg exited non-zero, reason in its log
echo --------------------------------
echo.
echo Logs: %LOGDIR%\
echo.
call "%~dp0rebuild_results_table.bat"
echo.
pause
exit /b 0

:fatal
echo.
echo FATAL: !MSG!
echo        Nothing has been run and nothing has been spent.
echo.
echo   Every preflight check branches on the four values printed above. Read
echo   them first - the usual causes are:
echo     - APPDATA is not your own profile: the window is elevated and looking
echo       in another profile, where the package is not installed. Run it
echo       without administrator rights.
echo     - py missing: Explorer hands a double-clicked window a different PATH
echo       than a terminal started from your profile. Run it from a terminal.
echo     - opencode missing: npm install -g --allow-scripts=opencode-ai opencode-ai
echo.
echo   PATH begins: !PATH:~0,200!
echo.
pause
exit /b 9

:leg
set "CFG=%~1"
echo.
echo ==== %CFG%  (%~2) ====

REM Evict whatever is resident before starting. Ollama holds a model for ~5 min
REM after use, so leg N+1 would otherwise start while leg N's weights are still
REM in memory. On 2026-09-11 that made gpt-oss-20b run 2.6x slower and produce
REM zero edits, then killed the 30B with APIError.
REM /offline, because findstr REFUSES a file carrying the offline attribute and
REM says so on stderr instead of reading it:
REM   FINDSTR: Dateien mit Offlineattribut wurden uebersprungen.
REM A OneDrive-synced tree sets that attribute, and it survived the move out of
REM OneDrive until the files were rehydrated. On 2026-09-12 that emptied
REM LEGMODEL, so the whole block below was skipped in silence: no eviction
REM before a leg, and no line saying so.
set "LEGMODEL="
set "LEGENGINE="
for /f "usebackq tokens=2 delims==" %%M in (`findstr /offline /b "MODEL=" ".llm_config.%CFG%"`) do set "LEGMODEL=%%M"
for /f "usebackq tokens=2 delims==" %%E in (`findstr /offline /b "ENGINE=" ".llm_config.%CFG%"`) do set "LEGENGINE=%%E"
REM Say it rather than skip it. An unread config is not a reason to abort - the
REM run itself reads the file through python and is unaffected - but it IS the
REM reason the previous leg's weights are still resident, and that shows up
REM later as a leg running 2.6x slow for no visible cause.
if not defined LEGMODEL (
  echo   WARNING: could not read MODEL= from .llm_config.%CFG% - no eviction ran.
  echo            The run itself is unaffected; a previous leg's model may still
  echo            be holding memory.
)
if defined LEGMODEL (
  REM The unload runs for every leg: a local model left resident by the previous
  REM leg holds its weights whether or not THIS leg wants them back.
  py -3 "%~dp0engine_leg.py" unload "!LEGMODEL!"
  REM Only a local model is pulled into RAM. Saying "pulled into RAM" before a
  REM claude or gpt leg claimed memory for a model that runs on someone else's
  REM hardware, and read as though two models were about to be loaded at once.
  if /i "!LEGENGINE!"=="opencode" (
    echo   load:   !LEGMODEL!  ^(local, pulled into RAM on its first request^)
  ) else (
    echo   model:  !LEGMODEL!  ^(cloud, nothing is loaded on this machine^)
  )
)

echo   start %TIME%
py -3 run_master.py !PROJECT! !METHODOLOGY! --config .llm_config.%CFG% > "%LOGDIR%\%CFG%_%STAMP%.log" 2>&1
set "RC=!ERRORLEVEL!"
echo   end   %TIME%  exit=!RC!

REM run_master exits 0 for any run that reached a row - including one that says
REM APIError and scores 0.0000. The exit code alone is not a pass signal, so
REM judge the row itself. The verdict is written to a file so its own exit code
REM survives (a for/f around it would swallow it) and its metrics line can be
REM both printed here and kept in the summary.
set "VERD=n/a"
if "!RC!"=="0" (
  set "VFILE=%LOGDIR%\verdict_%CFG%_%STAMP%.txt"
  py -3 "%~dp0engine_leg.py" verdict %CFG% > "!VFILE!" 2>&1
  set "VRC=!ERRORLEVEL!"
  if "!VRC!"=="0" (set "VERD=PASS") else if "!VRC!"=="1" (set "VERD=FAIL") else (set "VERD=UNKNOWN")
  for /f "usebackq delims=" %%L in ("!VFILE!") do echo   %%L
  for /f "usebackq delims=" %%L in ("!VFILE!") do echo %CFG%  %%L >> "%SUMMARY%"
) else (
  echo   --- last lines of log ---
  powershell -NoProfile -Command "Get-Content '%LOGDIR%\%CFG%_%STAMP%.log' -Tail 3 | ForEach-Object { '   ' + $_ }"
  set "VERD=ABORT"
)
echo %CFG%  exit=!RC!  !VERD!  (%~2) >> "%SUMMARY%"
exit /b 0
