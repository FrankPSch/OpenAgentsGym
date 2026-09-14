@echo off
setlocal enabledelayedexpansion
REM Fill the thin panels - p01, p02, p03 - with the arms that LEAD the two big projects, on every
REM local engine. Those three panels currently hold little more than m00_empty and m48_syntax_gate
REM per engine, so their charts show a handful of points and rank nothing.
REM
REM WHICH ARMS. The union of the top ten of the combined p04_python_xlarge panel and the top ten of
REM the combined p05_python_refactor_large panel, by sc_overall_ratio, read out of the table by
REM lib/top_arms.py at run time. Never pasted in here: the leaders move as rows arrive and a
REM hard-coded list would go on running last month's answer while looking current.
REM
REM WHY THOSE. An arm that leads where the projects discriminate is the arm worth spending a local
REM run on. The alternative - every arm on every small project - is four times the machine time for
REM rows nobody will read.
REM
REM   05_run_fill_small_projects.bat              print the plan and spend nothing
REM   05_run_fill_small_projects.bat /go          run it
REM   set FILL_TOP=5  before either                fewer arms per list (default 10)
REM   set FILL_PROJECTS=p01_python_small,p02_python_medium
REM   set FILL_ENGINES=e06_local_gptoss_20b e07_local_qwen3_4b
REM
REM COST, and read this before /go. A cell already holding a row is skipped (--min-rows 1 counts
REM the published table over every campaign), so this is only ever the gap. The gap on a fresh
REM table is about 18 arms x 3 projects x 5 engines, and local legs run 6-30 min on p01, 10-30 on
REM p02 and 20-60+ on p03. That is days of machine time, not an evening. Narrow it with FILL_TOP
REM and FILL_PROJECTS rather than starting the whole thing and killing it half way.
REM
REM A NOTE ON p03. qwen3-4b scores 0.0000 on every p03 row it has and qwen3-coder-30b APIErrors on
REM all of them; those legs will buy rows that say what the existing rows already say. p01 and p02
REM are where a local engine still produces a score, which is why FILL_PROJECTS exists.
REM
REM Safe to re-run after a kill, a rate limit or a bugcheck: the next call counts the table again
REM and runs only what is still missing. Nothing here is billed - the local engines are free and
REM the cloud ones are not touched.

if "%FILL_TOP%"=="" set "FILL_TOP=10"
if "%FILL_PROJECTS%"=="" set "FILL_PROJECTS=p01_python_small,p02_python_medium,p03_python_large"
if "%FILL_ENGINES%"=="" set "FILL_ENGINES=e06_local_gptoss_20b e07_local_qwen3_4b e08_local_qwen3coder_30b e11_local_qwen3coder_30b_tuned e12_local_devstral_24b"
set "SRC=p04_python_xlarge,p05_python_refactor_large"

REM %SRC% is quoted: unquoted, cmd reads the commas inside a for/f command as argument separators
REM and the script sees only the first project.
for /f "usebackq delims=" %%A in (`py -3 "%~dp0lib\top_arms.py" --projects "%SRC%" --top %FILL_TOP%`) do set "ARMS=%%A"
if "!ARMS!"=="" (echo could not read the leaders from results_repository.csv & exit /b 4)

echo === plan
echo   source panels = %SRC%   top %FILL_TOP% of each, by sc_overall_ratio
echo   arms          = !ARMS!
echo   projects      = %FILL_PROJECTS%
echo   engines       = %FILL_ENGINES%
echo   cells already holding a row are skipped (--min-rows 1)
echo.
if /i not "%~1"=="/go" (
  echo Nothing run. Pass /go to spend the machine time, or narrow it first:
  echo   set FILL_TOP=5 ^&^& set FILL_PROJECTS=p01_python_small,p02_python_medium
  exit /b 0
)

REM The local engines need opencode's real .exe on PATH: the npm .CMD shim on PATH cannot be
REM launched by CreateProcess, which is why every local batch resolves it the same way.
for /f "usebackq delims=" %%R in (`py -3 "%~dp0engine_find_opencode.py"`) do set "OCBIN=%%R"
if "!OCBIN!"=="NONE" (echo no launchable opencode.exe found & exit /b 6)
set "PATH=!OCBIN!;!PATH!"

REM Idle standby with a model resident bugchecked an unattended sweep on 2026-09-13 (0x19C), and
REM this batch is longer than that one was.
py -3 "%~dp0engine_nosleep.py" on

for %%C in (%FILL_ENGINES%) do (
  echo.
  echo === %%C
  for /f "usebackq tokens=2 delims==" %%M in (`findstr /offline /b "MODEL=" ".llm_config.%%C"`) do set "LEGMODEL=%%M"
  REM Asked before the legs, not after: a gateway serving a name Ollama does not have produces rows
  REM that look like model failures, which is the one thing this repository refuses to collect.
  py -3 "%~dp0gateway\_check_model.py" "!LEGMODEL!"
  if errorlevel 1 (
    echo   SKIPPED -- the gateway cannot serve !LEGMODEL!
  ) else (
    py -3 "%~dp0engine_leg.py" unload "!LEGMODEL!"
    py -3 "%~dp0engine_freeram.py"
    py -3 "%~dp0run_master.py" --matrix --config ".llm_config.%%C" --projects %FILL_PROJECTS% --methodologies !ARMS! --min-rows 1 --workers 1
    if errorlevel 1 echo   WARNING: %%C reported pairs without a row -- see the matrix log
  )
)

py -3 "%~dp0engine_nosleep.py" off
echo.
echo === consolidating
py -3 "%~dp0run_master.py" --consolidate
exit /b %ERRORLEVEL%
