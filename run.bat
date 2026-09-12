@echo off
if "%~2"=="" (echo usage: run.bat ^<project^> ^<methodology^> [--config ^<path^>] & exit /b 2)
REM Capability level 2 (.llm_config.model_02) unless the caller names another config.
if "%~3"=="" (set OPTS=--config .llm_config.model_02) else (set OPTS=%3 %4)
py -3 "%~dp0run_master.py" %1 %2 %OPTS%
set "RC=%ERRORLEVEL%"
REM Merge the row into the published table, as every batch that produces rows now
REM does. A run whose row stays in its run directory is invisible to --gate and to
REM any pivot, and the gap only shows up later as a table that is missing runs
REM someone remembers making. Consolidation is idempotent and keeps rows whose run
REM directory is gone, so running it after a single pair costs nothing.
REM The run's own exit code is preserved: the merge must not mask an aborted run.
call "%~dp0rebuild_results_table.bat"
exit /b %RC%
