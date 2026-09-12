@echo off
REM Turbo sweep: EVERY project x every methodology, once each, on capability level 1 (the
REM cheapest model, lowest effort) -- an apparatus check of the whole matrix, never ranked.
REM Sister of run_smoke_e02.bat: identical except for LEVEL and SCOPE.
REM Rows carry cfg_campaign=.llm_config.model_%LEVEL%; chapter 17 pools nothing across levels.
set LEVEL=01
set SCOPE=--matrix --workers 1
py -3 "%~dp0run_master.py" %SCOPE% --config .llm_config.model_%LEVEL%
set RC=%ERRORLEVEL%
call "%~dp0rebuild_results_table.bat"
exit /b %RC%
