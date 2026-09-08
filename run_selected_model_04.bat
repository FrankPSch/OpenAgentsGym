@echo off
REM Validity gate only -- chapter 16: the impossible project 00_fail against the empty, the sabotage
REM and the incumbent methodology, on capability level 4 (.llm_config.model_04). Add further pairs by hand.
set CFG=--config .llm_config.model_04
call "%~dp0run.bat" 00_fail 00_empty %CFG%
call "%~dp0run.bat" 00_fail 00_sabotage %CFG%
call "%~dp0run.bat" 00_fail 08_process_doctypes_roles_guardrails %CFG%
call "%~dp0rebuild_results_table.bat"
