@echo off
REM Shared helper: finds Python (any machine), installs the two libraries if missing. Sets PYEXE.
set "PYEXE="
REM portable copy: a private Python lives in the 'runtime' folder next to this file
if exist "%~dp0runtime\python.exe" set "PYEXE=%~dp0runtime\python.exe"
if defined PYEXE goto :found
if exist "%~dp0python_path.txt" set /p PYEXE=<"%~dp0python_path.txt"
if defined PYEXE if exist "%PYEXE%" goto :found
set "PYEXE="
for %%V in (314 313 312 311 310) do (
  if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
)
if defined PYEXE goto :found
for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
if defined PYEXE goto :found
for /f "delims=" %%P in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
if defined PYEXE goto :found
echo.
echo  Python was not found on this computer.
echo  Install Python 3 from python.org (tick "Add python.exe to PATH"), then run this again.
echo  Or write the full path of python.exe into a file called python_path.txt in this folder.
exit /b 1
:found
"%PYEXE%" -c "import pptx, openpyxl" >nul 2>&1
if errorlevel 1 (
  echo  Installing python-pptx and openpyxl - one time only...
  "%PYEXE%" -m pip install python-pptx openpyxl -q
)
exit /b 0
