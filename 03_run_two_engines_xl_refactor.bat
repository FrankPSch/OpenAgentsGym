@echo off
REM Bring every (project, methodology) cell of p04_python_xlarge and p05_python_refactor_large to
REM at least MIN_ROWS rows, and run nothing beyond that.
REM
REM --min-rows does the counting, so this file states the TARGET and not a run list. It counts the
REM published table as well as local\runs, over every campaign. A cell already at the minimum is
REM not run again. Nothing here is hard-coded from a particular state of the table, so the file
REM stays correct as rows accumulate.
REM
REM That is the difference from --skip-existing, which asks only whether THIS campaign produced a
REM row and reads local\runs alone. Run directories get cleared while published rows do not, so on
REM a cleaned machine --skip-existing sees an empty slate and re-runs the whole sweep.
REM
REM Each pass adds at most one row per cell, so two passes on two engines spread across both
REM rather than letting the first take the whole deficit. The second re-counts, so it runs only
REM the remainder. As the table stands: pass 1 queues 87, pass 2 queues 1 --
REM p05_python_refactor_large / m48_syntax_gate, the one cell in the matrix with no row at all,
REM which therefore ends with one row from each engine rather than two from one.
REM
REM The two are separate campaigns and are never pooled (chapter 17): each row carries its own
REM cfg_campaign. They also differ in model AND effort, so a difference between them cannot be
REM attributed to either alone -- this levels a table, it is not a controlled contrast.
REM
REM As the table stands: 88 cells, 86 holding one row, one holding three, one holding none.
REM 88 runs to level it. Sonnet is the cheaper model; opus averaged $1.59 on p04 and $0.71 on p05
REM against a $4.00 per-run cap, so budget roughly $30-40 and a couple of hours at 3 workers.
REM
REM Safe to re-run after a kill, a rate limit or a closed window: the next call counts again and
REM runs only what is still missing. Raise MIN_ROWS to 3 for the repeats chapter 17 asks for
REM before arms are compared.

setlocal
set PROJECTS=p04_python_xlarge,p05_python_refactor_large
set MIN_ROWS=2
set WORKERS=3

echo === pass 1: e13_claude_sonnet_5_medium over %PROJECTS%, target %MIN_ROWS% row(s) per cell
py -3 "%~dp0run_master.py" --matrix --config .llm_config.e13_claude_sonnet_5_medium --projects %PROJECTS% --min-rows %MIN_ROWS% --workers %WORKERS%
if errorlevel 1 echo WARNING: pass 1 reported pairs without a row -- see the matrix log

echo === pass 2: e03_claude_opus_5 tops up whatever is still short
py -3 "%~dp0run_master.py" --matrix --config .llm_config.e03_claude_opus_5 --projects %PROJECTS% --min-rows %MIN_ROWS% --workers %WORKERS%
if errorlevel 1 echo WARNING: pass 2 reported pairs without a row -- see the matrix log

echo === consolidating
py -3 "%~dp0run_master.py" --consolidate
exit /b %ERRORLEVEL%
