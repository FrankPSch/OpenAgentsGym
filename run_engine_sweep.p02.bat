@echo off
REM ===========================================================================
REM 03_p02_local_sweep.bat - every local engine on p02_python_medium, twice:
REM once with no methodology at all, once with the syntax gate.
REM
REM   03_p02_local_sweep.bat            local engines only, costs nothing
REM   03_p02_local_sweep.bat /billed    also claude and gpt
REM
REM WHAT IT IS FOR. m00_empty is the anchor: the same model, the same project,
REM no instructions. Every methodology claim is a claim about the DIFFERENCE
REM from that row, so a gate measured without its own anchor on the same day,
REM the same gateway and the same machine is not measurable at all.
REM
REM p02 is the size where this question is still answerable. At p03 four of the
REM five local arms score zero whatever the methodology, and at p04 all of them
REM do - a floor tells you nothing about a treatment. p02 is where gpt-oss-20b
REM sits near 0.88 and qwen3-4b near 0.93, so a gate has somewhere to move the
REM number in either direction.
REM
REM WHAT IS ALREADY KNOWN, so a repeat can be recognised as a repeat:
REM   gpt-oss-20b  m48: 0.8630 / 0.9020 / 0.8820   (three runs, 2026-09-12/13)
REM   qwen3-4b     m48: 0.8293 / 0.9350 / 0.9300
REM That spread - about 0.05 on identical cells - IS the noise floor. A single
REM new row inside it is not a result, which is the reason this batch exists as
REM a pair rather than as one more run of the gate on its own.
REM
REM THE ARMS. e06 and e07 produce rows. e08 has never loaded on this machine
REM (the Vulkan allocator refuses a 1 GiB buffer at 32768 context) and is kept
REM as the ceiling measurement it is. e11 is the same weights at ctx8k/gpu10
REM and does load. e12 is devstral, unproven here as of 2026-09-13; if its tag
REM is missing the per-leg preflight skips it rather than writing a row that
REM measures the omission.
REM
REM TIME. Ten local legs. p02 legs have run 5-30 minutes each, e08 fails in
REM about four minutes, so budget THREE TO FIVE HOURS unattended. The two cloud
REM legs, if you pass /billed, add about a minute each and cost real money.
REM
REM BEFORE STARTING:
REM   - 01_build_models.bat, so every tag exists and reports a tools capability
REM   - 02_start_gateway.bat, and read its model list: a name without an Ollama
REM     tag behind it, or a gateway still serving an older config, is the
REM     failure that looks exactly like a model failure
REM   - close anything large; free RAM decides whether the 24B and 30B arms page
REM
REM The matrix consolidates after each half, so the table is current even if you
REM stop the window between them.
REM ===========================================================================
setlocal
cd /d "%~dp0"

REM Forward /billed only when it was actually asked for. An empty argument is
REM not harmless: it arrives as a positional and the matrix reads it as one.
set "EXTRA="
if /i "%~1"=="/billed" set "EXTRA=/billed"

REM The matrix and the table rebuild both pause at the end so a double-clicked
REM window keeps its summary. Across two halves and several hours that is a
REM stall nobody is watching, so tell them this is a campaign.
set "OAG_CAMPAIGN=1"

echo ============================================================
echo  sweep: p02_python_medium, all local engines
echo  arm 1: m00_empty          (the anchor - no instructions)
echo  arm 2: m48_syntax_gate    (the treatment)
echo  billed legs: %EXTRA%    (empty = local only)
echo  started %DATE% %TIME%
echo ============================================================

call "%~dp0run_engine_matrix.p02.bat" m00_empty %EXTRA%
call "%~dp0run_engine_matrix.p02.bat" m48_syntax_gate %EXTRA%

set "OAG_CAMPAIGN="

echo.
echo ============================================================
echo  sweep finished %DATE% %TIME%
echo.
echo  HOW TO READ IT. Compare each engine against ITSELF across the two
echo  arms, never one engine against another - cfg_model is a campaign
echo  constant and those rows do not pool.
echo.
echo  A difference smaller than about 0.05 is inside the noise measured on
echo  this cell and is not a result. What would be a result: a zero that
echo  becomes a score, or a score that becomes a zero.
echo.
echo  res_syntax_ok is the column that says whether the gate had anything
echo  to bite on. A run that was already syntactically clean cannot have
echo  been helped by a syntax gate, however its score moved.
echo ============================================================
pause
exit /b 0
