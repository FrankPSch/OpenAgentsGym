@echo off
REM Full matrix: every methodology on every project, on capability level 3 (.llm_config.model_03).
REM 40 methodologies x 6 projects = 240 calls, each REPEATS times.
REM Directory listings, not a hard-coded list -- a new project or methodology joins the matrix by
REM existing, which is what run_turbo_model_01.bat already does. Repeats come from REPEATS in the
REM config, not from this file.
REM The matrix is --matrix in run_master.py -- one implementation for both sweeps, which also
REM consolidates and prints the chapter 16 gate when it is done. --workers 1 is the sequential
REM order the two nested for /d loops had; raise it to run pairs side by side.
py -3 "%~dp0run_master.py" --matrix --config .llm_config.model_03 --workers 1
exit /b %ERRORLEVEL%
