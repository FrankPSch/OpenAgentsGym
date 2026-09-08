@echo off
REM Smoke test: ONE pair on capability level 2 (the workhorse model) -- the quickest proof the
REM whole chain works at the level run.bat uses.
REM Sister of run_turbo_model_01.bat: identical except for LEVEL and SCOPE.
REM Rows carry cfg_campaign=.llm_config.model_%LEVEL%; chapter 17 pools nothing across levels.
set LEVEL=02
set SCOPE=02_python_medium 00_empty
py -3 "%~dp0run_master.py" %SCOPE% --config .llm_config.model_%LEVEL%
set RC=%ERRORLEVEL%
call "%~dp0rebuild_results_table.bat"
exit /b %RC%
