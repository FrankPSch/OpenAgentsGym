@echo off
REM Stage everything, commit with the message given as arguments (or a timestamp), push to origin.
REM Usage: git_push.bat [commit message words...]      Nothing to commit is not an error.
cd /d "%~dp0"
set MSG=%*
if "%MSG%"=="" for /f "tokens=1-3 delims=/.- " %%a in ("%DATE%") do set MSG=update %%c-%%b-%%a %TIME:~0,5%
git add -A
git diff --cached --quiet || git commit -q -m "%MSG%"
git push origin HEAD
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo git_push: push failed (exit %RC%) -- run git_pull.bat first if origin moved
pause
exit /b %RC%
