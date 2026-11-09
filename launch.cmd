@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 "%~dp0clock_gui.pyw" %*
goto done
:python
python "%~dp0clock_gui.pyw" %*
:done
if errorlevel 1 pause
