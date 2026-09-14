@echo off
setlocal enabledelayedexpansion
REM Give the two QuantConnect tiers - p06_qc_ema_cross and p07_qc_bugfix_refactor - one row each
REM for sixteen named arms, PER ENGINE, on sonnet at medium and opus at low.
REM
REM   06_run_qc_tiers.bat              print the plan and spend nothing
REM   06_run_qc_tiers.bat /go          run the two billed engines
REM   06_run_qc_tiers.bat /go /local   also run e11 (qwen3-coder-30b-tuned) -- read the warning
REM   set QC_ARMS=00,34,47             a different list (numbers, m34, or full names)
REM
REM PER ENGINE is the point, and it is why this does not use --min-rows. That switch counts rows
REM over EVERY campaign, which is right for levelling a table and wrong here: p06/m00_empty already
REM has an opus row, so --min-rows would skip it for sonnet too and the sonnet panel would keep the
REM hole this batch exists to fill. lib/missing_cells.py asks the narrower question instead -- does
REM THIS campaign hold a row for this pair - and the loop runs only what comes back.
REM
REM COST, from the eleven p06/p07 rows already in the table: $0.73-1.42 and 90-240 s per run. The
REM gap as this is written is 24 cells on opus and 32 on sonnet, so roughly $55-75 and two to three
REM hours for the two billed engines. Both are billed legs; nothing here is free.
REM
REM WARNING ON /local, and it is not a formality. p06 and p07 are the only projects whose task is
REM to drive the QuantConnect MCP tools, and the harness passes --mcp-config on the CLAUDE launch
REM line alone (run_master.py, claude_implementer_argv). Under ENGINE=opencode there is no MCP
REM server, so e11 would attempt a task whose whole content is calling tools it cannot see. Those
REM rows would measure the harness rather than the model, which is the one thing this repository
REM refuses to collect - "a row that measures the harness is worse than no row". The flag exists
REM because it was asked for; run it to see what that failure looks like, not to rank anything,
REM and expect res_diff_lines=0 with a verification failure on all 32.
REM
REM Safe to re-run: the next call re-reads the table and runs only what is still missing.

set "ARMS=%QC_ARMS%"
if "!ARMS!"=="" set "ARMS=00,34,47,08,03,12,38,36,18,01,44,29,19,28,15,32"
set "PROJECTS=p06_qc_ema_cross,p07_qc_bugfix_refactor"
set "BILLED=e13_claude_sonnet_5_medium e03_claude_opus_5"
set "LOCAL=e11_local_qwen3coder_30b_tuned"

set "GO="
set "WITHLOCAL="
for %%A in (%*) do (
  if /i "%%A"=="/go" set "GO=1"
  if /i "%%A"=="/local" set "WITHLOCAL=1"
)

set "ENGINES=%BILLED%"
if defined WITHLOCAL set "ENGINES=%BILLED% %LOCAL%"

echo === plan
echo   projects = %PROJECTS%
echo   arms     = !ARMS!
echo   engines  = !ENGINES!
echo.
set /a TOTAL=0
for %%C in (!ENGINES!) do (
  for /f %%N in ('py -3 "%~dp0lib\missing_cells.py" --campaign ".llm_config.%%C" --projects "%PROJECTS%" --methodologies "!ARMS!" ^| find /c /v ""') do (
    echo   %%C: %%N cell^(s^) without a row
    set /a TOTAL+=%%N
  )
)
echo   total    = !TOTAL! run(s)
echo.
if not defined GO (
  echo Nothing run. Pass /go to spend it. The billed engines cost about $1 per run.
  exit /b 0
)

REM Idle standby with a run in flight bugchecked an unattended sweep on 2026-09-13.
py -3 "%~dp0engine_nosleep.py" on
if defined WITHLOCAL (
  for /f "usebackq delims=" %%R in (`py -3 "%~dp0engine_find_opencode.py"`) do set "OCBIN=%%R"
  if not "!OCBIN!"=="NONE" set "PATH=!OCBIN!;!PATH!"
)

for %%C in (!ENGINES!) do (
  echo.
  echo === %%C
  REM The gap is re-read per engine, immediately before its legs: an earlier engine in this same
  REM loop cannot have filled a cell of a later one - a row carries its own campaign - but a
  REM concurrent run or an earlier kill can, and re-reading costs nothing.
  for /f "usebackq tokens=1,2" %%P in (`py -3 "%~dp0lib\missing_cells.py" --campaign ".llm_config.%%C" --projects "%PROJECTS%" --methodologies "!ARMS!"`) do (
    echo   --- %%P %%Q
    py -3 "%~dp0run_master.py" %%P %%Q --config ".llm_config.%%C"
    if errorlevel 1 echo       WARNING: no row -- see that run's abort.txt
  )
)

py -3 "%~dp0engine_nosleep.py" off
echo.
echo === consolidating
py -3 "%~dp0run_master.py" --consolidate
exit /b %ERRORLEVEL%
