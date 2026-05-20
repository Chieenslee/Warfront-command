@echo off
setlocal

cd /d "%~dp0"
title Warfront Command - RUN ALL

echo ============================================
echo  WARFRONT COMMAND
echo ============================================
echo.

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

echo Using: %PYTHON_EXE%
echo Checking pygame...
%PYTHON_EXE% -c "import pygame; print('pygame ok', pygame.version.ver)" || goto :missing

echo.
echo Starting game...
%PYTHON_EXE% -m warfront
goto :done

:missing
echo.
echo Pygame is missing or Python cannot start this project.
echo Try:
echo   python -m pip install -r requirements.txt
echo.

:done
echo.
echo Game closed. Press any key to exit.
pause >nul
