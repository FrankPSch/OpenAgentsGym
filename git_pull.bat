@echo off
REM Fetch and fast-forward the current branch from origin. Refuses (exit 1) if local commits
REM diverge from origin, so nothing is merged or rewritten silently; run git_push.bat first then.
cd /d "%~dp0"
git pull --ff-only
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo git_pull: not fast-forwardable or offline (exit %RC%)
pause
exit /b %RC%
