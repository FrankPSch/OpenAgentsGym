@echo off
REM Full matrix: every methodology on every project, on capability level 4 (.llm_config.e04_claude_fable_5_1).
REM 43 methodologies x 6 projects = 258 calls; *_outdated directories are skipped., each REPEATS times.
REM Directory listings, not a hard-coded list -- a new project or methodology joins the matrix by
REM existing, which is what run_turbo_e01.bat already does. Repeats come from REPEATS in the
REM config, not from this file.
REM The matrix is --matrix in run_master.py -- one implementation for both sweeps, which also
REM consolidates and prints the chapter 16 gate when it is done. --workers 1 is the sequential
REM order the two nested for /d loops had; raise it to run pairs side by side.
py -3 "%~dp0run_master.py" --matrix --config .llm_config.e04_claude_fable_5_1 --workers 1
exit /b %ERRORLEVEL%
