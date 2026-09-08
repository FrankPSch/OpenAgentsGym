@echo off
if "%~2"=="" (echo usage: run.bat ^<project^> ^<methodology^> [--config ^<path^>] & exit /b 2)
REM Capability level 2 (.llm_config.model_02) unless the caller names another config.
if "%~3"=="" (set OPTS=--config .llm_config.model_02) else (set OPTS=%3 %4)
py -3 "%~dp0run_master.py" %1 %2 %OPTS%
exit /b %ERRORLEVEL%
