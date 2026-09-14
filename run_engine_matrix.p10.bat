@echo off
REM ===========================================================================
REM The engine matrix for p10_python_swe_xarray_7233, with the no-methodology anchor.
REM
REM This is a one-line wrapper. The matrix itself - preflight, the billed
REM opt-in, the per-leg unload, the verdict and the consolidation - lives in
REM run_engine_matrix.bat and is maintained in exactly one place. Nine copies
REM of two hundred lines would drift apart the first time one of them was
REM fixed, and the split into per-project files exists only so a project can
REM be started by double-clicking rather than by remembering an argument.
REM
REM USAGE
REM   run_engine_matrix.p10.bat            local engines, m00_empty
REM   run_engine_matrix.p10.bat 29_x       another methodology
REM   run_engine_matrix.p10.bat /billed    also the two cloud legs
REM
REM Anything passed here is forwarded, so the first positional argument lands
REM on the methodology and /billed is recognised wherever it sits.
REM ===========================================================================
call "%~dp0run_engine_matrix.bat" p10_python_swe_xarray_7233 %*
exit /b %ERRORLEVEL%
