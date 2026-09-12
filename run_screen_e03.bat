@echo off
REM Screen: every methodology once on ONE project, capability level 3 (.llm_config.e03_claude_opus_5).
REM The first stage of the two-stage design: every arm on the xlarge project, one repeat, then the
REM best few go to level 4 with repeats. --skip-existing makes the line resumable after a limit
REM or a kill; --workers 3 runs three pairs side by side.
set PROJECT=p04_python_xlarge
py -3 "%~dp0run_master.py" --matrix --config .llm_config.e03_claude_opus_5 --projects %PROJECT% --workers 3 --skip-existing
exit /b %ERRORLEVEL%
