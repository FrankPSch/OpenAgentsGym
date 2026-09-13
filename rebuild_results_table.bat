@echo off
REM Rebuilds results_repository.csv (repo root) from every local\runs\*\results_run.csv and the
REM results_pareto.svg cost/score chart beside it (chapter 13.2), then prints the chapter 16
REM validity gate over it, per campaign. Safe to run any time.
py -3 "%~dp0run_master.py" --consolidate
echo.
py -3 "%~dp0run_master.py" --gate
echo.
REM Guarded, because every matrix calls this batch at the end of a project. A
REM campaign spanning three projects would otherwise stop here, after the gate
REM output, with nobody watching - which is exactly what happened on
REM 2026-09-12: p03 sat waiting two and a half hours for a keypress.
if not defined OAG_CAMPAIGN pause
