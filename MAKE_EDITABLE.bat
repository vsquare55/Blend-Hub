@echo off
rem Makes the EDITABLE single-file HTML of the whole Blend Hub (for a Mac / any browser) with today's data -> "Editable HTML" folder.
cd /d "%~dp0"
call "%~dp0_python.bat"
if errorlevel 1 (pause & exit /b 1)
"%PYEXE%" -X utf8 scripts\make_editable.py
echo.
echo  Done - Editable HTML\Blend_Hub_Editable.html is ready. Send that file (and READ_ME.txt) to anyone.
pause
