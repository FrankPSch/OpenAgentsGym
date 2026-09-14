@echo off
REM Three runs each of the sabotage anchor and the incumbent, on p04_python_xlarge under
REM e13_claude_sonnet_5_medium. Six runs. It answers one question and no other:
REM
REM   does p04 discriminate under this engine at all?
REM
REM Why it is worth six runs. The 87-row e13 sweep of 2026-09-14 put m47_sabotage at 1.0000 on
REM p04 -- joint top, above m29 at 0.9380 -- and the rank correlation against the opus campaign
REM over the 43 shared arms is 0.173. Two readings fit that equally well from single runs: the
REM arms genuinely reorder under a different model, or p04 under this engine has stopped
REM separating arms and the 0.80-1.00 spread is draw-to-draw variation. Three runs of the two
REM extreme arms tell them apart, and nothing cheaper does.
REM
REM Read it as: the range of the three sabotage scores against the range of the three incumbent
REM scores. Overlapping ranges mean this engine cannot rank arms on this project, and the e13
REM rows are then a cost-and-timing dataset rather than a quality one. Separated ranges give a
REM noise floor for the engine and make the ranking readable. The +/-0.05 floor quoted elsewhere
REM was measured on p02 against local models and does not transfer here.
REM
REM MECHANISM, and why it is a loop rather than REPEATS=3. REPEATS lives in the engine config,
REM and an .llm_config that has published rows is never edited (chapter 9) -- while copying it to
REM a new file would give the six rows a different cfg_campaign and stop them pooling with the 87
REM they exist to explain. Six separate invocations of the same unmodified config keep one label
REM and one set of constants, which is what chapter 17 asks for.
REM
REM Cost: sonnet at medium effort, and today's p04 legs under it ran 180-760 s each. Budget
REM roughly half an hour and a few dollars. Serial on purpose: three concurrent runs of one cell
REM would share the machine's memory and CPU with each other, and prf_duration_s is one of the
REM three terms sc_effort is built from.
REM
REM Safe to re-run: every invocation writes its own run directory and its own row. Running it
REM twice gives six rows per arm, which is better, not broken.

setlocal
set CFG=.llm_config.e13_claude_sonnet_5_medium
set PRJ=p04_python_xlarge
set N=3

for %%M in (m47_sabotage m29_invariants_test_first_relative_stop) do (
  for /L %%I in (1,1,%N%) do (
    echo === %%M  run %%I of %N%  [%PRJ%, %CFG%]
    py -3 "%~dp0run_master.py" %PRJ% %%M --config %CFG%
    if errorlevel 1 echo WARNING: %%M run %%I did not produce a row -- see its abort.txt
  )
)

echo === consolidating
py -3 "%~dp0run_master.py" --consolidate

echo.
echo === the six rows, by arm
py -3 "%~dp0lib\show_noise_floor.py"
exit /b %ERRORLEVEL%
