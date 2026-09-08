@echo off
REM Rebuilds results_repository.csv (repo root) from every local\runs\*\results_run.csv, then prints the chapter 16
REM validity gate over it, per campaign. Safe to run any time.
py -3 "%~dp0run_master.py" --consolidate
echo.
py -3 "%~dp0run_master.py" --gate
echo.
pause
