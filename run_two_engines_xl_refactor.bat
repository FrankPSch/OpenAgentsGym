@echo off
REM Two engines over two projects, so every (project, methodology) cell of p04_python_xlarge and
REM p05_python_refactor_large carries two rows: opus low (e03) and sonnet medium (e13).
REM
REM The two halves differ in model AND effort, so a difference between them cannot be attributed
REM to either on its own -- they are two engines measured side by side, not a controlled contrast.
REM Holding effort fixed would need a sonnet-at-low config.
REM
REM e13 is the same model and effort as e02 and exists only to give this sweep a campaign label of
REM its own, so its rows are never pooled with the published e02 rows.
REM
REM The two engines are two campaigns and are never pooled (chapter 17): each row carries its own
REM cfg_campaign. The sc_* score columns are computed per project across the whole table, so the
REM two engines land on one comparable scale without being merged into one population.
REM
REM READ THIS BEFORE RAISING E03_METHODOLOGIES:
REM --skip-existing decides what to run from local\runs\*\results_run.csv, NOT from
REM results_repository.csv. Run directories get cleared; published rows do not. So on a machine
REM whose run directories have been cleaned, --skip-existing sees nothing and re-runs pairs the
REM published table already holds. e03 already covers 43 of the 44 live methodologies on both
REM projects -- only m48_syntax_gate is missing -- which is why its half of this file names that
REM one arm explicitly instead of sweeping. Set E03_METHODOLOGIES to a comma list to add arms, or
REM blank it to sweep all 44 (~88 runs, ~$100 at the measured $1.59/$0.71 per-run means).
REM
REM Scale as it stands: 2 e03 runs + 88 e13 runs. Sonnet is the cheaper model, so budget roughly
REM $30-40 and a couple of hours at --workers 3, against ~$150 for the full double sweep.
REM
REM Resumable: re-running this file after a kill, a rate limit or a closed window costs nothing
REM but the run in flight -- for the e13 half, whose run directories are all still to be made.
REM The final consolidation is done here; --matrix also prints the chapter 16 validity gate.

setlocal
set PROJECTS=p04_python_xlarge,p05_python_refactor_large
set E03_METHODOLOGIES=m48_syntax_gate

echo === e03_claude_opus_5 (opus, low) over %PROJECTS%
if defined E03_METHODOLOGIES (
  py -3 "%~dp0run_master.py" --matrix --config .llm_config.e03_claude_opus_5 --projects %PROJECTS% --methodologies %E03_METHODOLOGIES% --workers 3 --skip-existing
) else (
  py -3 "%~dp0run_master.py" --matrix --config .llm_config.e03_claude_opus_5 --projects %PROJECTS% --workers 3 --skip-existing
)
if errorlevel 1 echo WARNING: the e03 half reported pairs without a row -- see the matrix log

echo === e13_claude_sonnet_5_medium (sonnet, medium) over %PROJECTS%
py -3 "%~dp0run_master.py" --matrix --config .llm_config.e13_claude_sonnet_5_medium --projects %PROJECTS% --workers 3 --skip-existing
if errorlevel 1 echo WARNING: the e13 half reported pairs without a row -- see the matrix log

echo === consolidating
py -3 "%~dp0run_master.py" --consolidate
exit /b %ERRORLEVEL%
