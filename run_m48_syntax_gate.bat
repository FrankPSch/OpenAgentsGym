@echo off
REM ===========================================================================
REM m48_syntax_gate across the three sized Python projects.
REM
REM   run_m48_syntax_gate.bat            local engines only, costs nothing
REM   run_m48_syntax_gate.bat /billed    also claude and gpt
REM
REM WHAT IT IS FOR. m48_syntax_gate was written on 2026-09-12 against an
REM observed failure: three local runs scored 0.0000 while writing 51 to 147
REM diff lines, each because one file would not parse. Its first run answered
REM on p02_python_medium -- gpt-oss-20b went from 0.0000 (unterminated
REM triple-quoted string) to 0.8490 PASS, while claude-sonnet-5 was unchanged
REM within noise (0.9420 -> 0.9350), which is what a model that was not making
REM that mistake should do.
REM
REM One repeat is not a result. This batch takes the same arm across three
REM project sizes so the question becomes whether the gate holds as the task
REM grows, and pairs every cell with the m00_empty rows already in the table.
REM
REM TIME. Four local legs per project, three projects. Local legs have run
REM between 16 and 45 minutes each, and the two 30B legs are the slowest, so
REM budget SIX TO TEN HOURS unattended. The cloud legs add about a minute each.
REM
REM BEFORE STARTING, two things that have each cost a run today:
REM   - restart LiteLLM if you have not since e11 was added, or its leg fails at
REM     the gateway and reads like a model failure:
REM       litellm --config <repo>\litellm\config.yaml --port 4000
REM   - close anything large. Free RAM decides whether the 30B pages from disk;
REM     18 GB of weights against 8 GB free measured 0.76 tok/s, which is the
REM     SSD, not the model.
REM
REM Each project batch consolidates its own rows, so the table is current after
REM every project rather than only at the end. Stopping the window between
REM projects is therefore safe and loses nothing already measured.
REM ===========================================================================
setlocal
cd /d "%~dp0"

set "M=m48_syntax_gate"
set "BILLED=%~1"

echo ============================================================
echo  campaign: %M% on p02, p03, p04
echo  billed legs: %BILLED%    (empty = local only)
echo  started %DATE% %TIME%
echo ============================================================

call "%~dp0run_engine_matrix.p02.bat" %M% %BILLED%
call "%~dp0run_engine_matrix.p03.bat" %M% %BILLED%
call "%~dp0run_engine_matrix.p04.bat" %M% %BILLED%

echo.
echo ============================================================
echo  campaign finished %DATE% %TIME%
echo  Rows are consolidated: each project batch merged its own.
echo  Read them against the m00_empty rows for the same cells.
echo ============================================================
pause
exit /b 0
