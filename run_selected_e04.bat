@echo off
REM Validity gate only -- chapter 16: the impossible project p00_fail against the empty, the sabotage
REM and the incumbent methodology, on capability level 4 (.llm_config.e04_claude_fable_5_1). Add further pairs by hand.
set CFG=--config .llm_config.e04_claude_fable_5_1
call "%~dp0run.bat" p00_fail m00_empty %CFG%
call "%~dp0run.bat" p00_fail m47_sabotage %CFG%
call "%~dp0run.bat" p00_fail m08_process_doctypes_roles_guardrails %CFG%
call "%~dp0rebuild_results_table.bat"
