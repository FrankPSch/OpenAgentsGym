@echo off
REM ---------------------------------------------------------------------------
REM start_gateway.bat - bring up the LiteLLM protocol gateway on port 4000.
REM
REM Double-click this after a reboot, wait for the model list, then run a
REM campaign batch. The gateway keeps running in its own minimised window;
REM close that window to stop it.
REM
REM Three things this does that a bare `litellm --config ...` does not:
REM
REM   1. It frees port 4000 first. LiteLLM does NOT fail when the port is
REM      taken - it binds a random free port instead and says so only in its
REM      last line. The stale instance then keeps answering the engines with
REM      the config it booted from, which can be days old. That is a whole
REM      campaign measured against the wrong model list, with no error
REM      anywhere.
REM   2. It forces UTF-8. On a cp1252 console LiteLLM dies inside click.echo
REM      printing its own ASCII-art banner, before serving anything.
REM   3. It waits, and reports WHICH models are served - not merely that
REM      something answered. See gateway\_wait.py.
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PORT=4000"
set "MASTERKEY=sk-oag-local"
set "LOG=%~dp0gateway\gateway.log"

REM LiteLLM prints a banner that cannot be encoded in cp1252.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo.
echo   OpenAgentsGym - LiteLLM gateway
echo   config: gateway\config.yaml    port: %PORT%
echo.

REM --- free the port ---------------------------------------------------------
REM Matched on the port rather than on the state word, because the state word
REM is localised (ABHOEREN / LISTENING) and would not match on every machine.
REM PID 0 rows are TIME_WAIT leftovers, not listeners.
set "KILLED=0"
for /f "tokens=2,5" %%A in ('netstat -ano ^| findstr /r /c:":%PORT% "') do (
  echo %%A | findstr /r /c:":%PORT%$" >nul
  if not errorlevel 1 if not "%%B"=="0" (
    echo   stale listener on port %PORT% ^(PID %%B^) - stopping it
    taskkill /PID %%B /F >nul 2>&1
    set "KILLED=1"
  )
)
if "!KILLED!"=="1" timeout /t 2 /nobreak >nul

REM --- launch ----------------------------------------------------------------
if not exist "%~dp0gateway\config.yaml" (
  echo   FATAL: gateway\config.yaml not found.
  echo   Run this batch from the repository, not from a copy elsewhere.
  goto :end
)

echo   starting...
start "OAG LiteLLM gateway" /min cmd /c "py -3 -P "%~dp0gateway\_serve.py" --config "%~dp0gateway\config.yaml" --port %PORT% > "%LOG%" 2>&1"

REM --- wait, and say what is actually served ---------------------------------
py -3 "%~dp0gateway\_wait.py" %PORT% %MASTERKEY% 60
if errorlevel 1 (
  echo.
  echo   The gateway did not come up. Leave it stopped and read %LOG%.
  goto :end
)

echo.
echo   Ready. Leave the minimised "OAG LiteLLM gateway" window open,
echo   then start a campaign, e.g. run_m48_syntax_gate.bat
echo.

:end
endlocal
pause
