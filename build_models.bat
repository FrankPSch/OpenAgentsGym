@echo off
REM ---------------------------------------------------------------------------
REM build_models.bat - build every tuned Ollama tag this repository defines.
REM
REM A tuned tag is a MEASUREMENT CONSTANT, not a convenience. e11 differs from
REM e08 only by num_ctx and num_gpu, so the Modelfile is what its published
REM rows mean. Keeping the build here, from the versioned Modelfile, is what
REM makes those rows reproducible on another machine.
REM
REM Run this once after cloning, and again whenever a Modelfile changes. It is
REM cheap to repeat: ollama reuses the existing weight layers and only rewrites
REM the manifest.
REM
REM It is deliberately NOT part of start_gateway.bat. Starting a gateway and
REM building a model are different acts: one is done every session, the other
REM when a definition changes. start_gateway.bat checks that the tags exist and
REM names this batch when they do not.
REM
REM Naming: gateway\Modelfile.<name> builds the tag that config.yaml refers to
REM as ollama_chat/<name with the last dash before the size-suffix restored>.
REM In practice the mapping is spelled out below rather than derived, because a
REM clever derivation that guesses one tag wrong builds the wrong model and
REM every row after it is mislabelled.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

echo.
echo   OpenAgentsGym - building tuned model tags
echo.

where ollama >nul 2>&1
if errorlevel 1 (
  echo   FATAL: ollama not found on PATH.
  echo          Install it first - see oam_install.md section 2.
  goto :end
)

call :build qwen3-coder:30b-tuned gateway\Modelfile.qwen3-coder-30b-tuned

echo.
echo   Tags Ollama now holds:
ollama list
echo.
echo   Next: start_gateway.bat  (it verifies every served name against this list)
echo.
goto :end

REM --- build one tag ---------------------------------------------------------
:build
set "TAG=%~1"
set "MF=%~2"
if not exist "%~dp0%MF%" (
  echo   SKIP %TAG% - %MF% not found
  exit /b 0
)
echo   building %TAG%  from %MF%
ollama create %TAG% -f "%~dp0%MF%"
if errorlevel 1 (
  echo   FAILED %TAG% - see the message above
  exit /b 1
)
echo   ok %TAG%
echo.
exit /b 0

:end
endlocal
pause
