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
REM BEFORE STARTING, three things that have each cost a run:
REM   - start the gateway with 02_start_gateway.bat and read the model list it
REM     prints. A gateway that is merely up is not enough: a stale instance
REM     keeps port 4000 with the config it booted from, and the leg then fails
REM     at the gateway and reads like a model failure.
REM   - build the tuned tag once, or e11 fails in about a second with
REM     UnknownError -- LiteLLM serves the NAME, Ollama must hold the TAG:
REM       ollama create qwen3-coder:30b-tuned -f .\gateway\Modelfile.qwen3-coder-30b-tuned
REM     Check with: ollama list
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

REM Forward /billed only when it was actually asked for. Passing an empty
REM argument through is not harmless: it arrives as a positional and the
REM matrix reads it as one.
set "EXTRA="
if /i "%~1"=="/billed" set "EXTRA=/billed"

REM The matrix pauses at the end of every project so a double-clicked window
REM keeps its summary. Across three projects and six to ten hours that is a
REM stall, not a safety net, so tell it this is a campaign.
set "OAG_CAMPAIGN=1"


REM --- keep the machine awake --------------------------------------------------
REM An unattended sweep took the machine down on 2026-09-13: standby-after-60-min
REM fired mid-leg, and a power transition with 18 GB of weights resident and the
REM iGPU loaded cannot finish inside the win32k watchdog (bugcheck 0x19C). The
REM leg left a START with no DONE and no row. The power plan is a machine
REM setting that does not travel with the repository, so the campaign defends
REM itself and puts the value back at the end.
for /f "usebackq delims=" %%S in (`py -3 "%~dp0engine_nosleep.py" save`) do set "PREV_SLEEP=%%S"
py -3 "%~dp0engine_nosleep.py" off

echo ============================================================
echo  campaign: %M% on p02, p03, p04
echo  billed legs: %EXTRA%    (empty = local only)
echo  started %DATE% %TIME%
echo ============================================================

call "%~dp0run_engine_matrix.p02.bat" %M% %EXTRA%
call "%~dp0run_engine_matrix.p03.bat" %M% %EXTRA%
call "%~dp0run_engine_matrix.p04.bat" %M% %EXTRA%

echo.
echo ============================================================
echo  campaign finished %DATE% %TIME%
echo  Rows are consolidated: each project batch merged its own.
echo  Read them against the m00_empty rows for the same cells.
echo ============================================================
py -3 "%~dp0engine_nosleep.py" restore %PREV_SLEEP%
set "OAG_CAMPAIGN="
pause
exit /b 0
