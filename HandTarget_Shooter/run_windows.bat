@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "ACTION=%~1"
set "CAMERA_NUM=%~2"
if not defined CAMERA_NUM set "CAMERA_NUM=0"
echo.
echo ===============================================
echo    RiG++ HAND TARGET SHOOTER - Windows

echo ===============================================
echo.
set "PYTHON_CMD="
set "CONDA_PY=%USERPROFILE%\anaconda3\python.exe"
if exist "%CONDA_PY%" (
    "%CONDA_PY%" -c "import sys,struct; exit(0 if (3,9) <= sys.version_info[:2] <= (3,14) and struct.calcsize('P')==8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=%CONDA_PY%"
)
if not defined PYTHON_CMD (
    python -c "import sys,struct; exit(0 if (3,9) <= sys.version_info[:2] <= (3,14) and struct.calcsize('P')==8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    py -3 -c "import sys,struct; exit(0 if (3,9) <= sys.version_info[:2] <= (3,14) and struct.calcsize('P')==8 else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD goto python_missing
set "ENV_PY=.venv\Scripts\python.exe"
if not exist "%ENV_PY%" (
  echo [1/3] Creating private Python environment ...
  if /I "%PYTHON_CMD%"=="python" (
    python -m venv .venv
  ) else if /I "%PYTHON_CMD%"=="py -3" (
    py -3 -m venv .venv
  ) else (
    "%PYTHON_CMD%" -m venv .venv
  )
  if errorlevel 1 goto failed
)
if not exist "%ENV_PY%" goto failed
echo [2/3] Installing game packages ...
"%ENV_PY%" -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto failed
if /I "%ACTION%"=="demo" goto demo
if /I "%ACTION%"=="test" goto tests
echo [3/3] Downloading hand model if necessary ...
"%ENV_PY%" download_model.py
if errorlevel 1 goto failed
echo Starting camera %CAMERA_NUM% ...
echo Default: move INDEX fingertip steadily to AIM, flick it up QUICKLY to FIRE.
echo Press - for easier firing, A for more aim assist.
"%ENV_PY%" main.py --camera %CAMERA_NUM%
if errorlevel 1 goto failed
goto done
:demo
echo [3/3] Starting demo using mouse instead of camera ...
"%ENV_PY%" main.py --demo
if errorlevel 1 goto failed
goto done
:tests
echo [3/3] Running automated tests ...
"%ENV_PY%" -m unittest discover -s tests -v
if errorlevel 1 goto failed
goto done
:python_missing
echo ERROR: 64-bit Python 3.9-3.14 could not be found.
echo Install Python or fix Windows PATH.
goto end
:failed
echo.
echo ERROR: Game startup failed. Please send the error text above.
goto end
:done
echo.
echo Finished successfully.
:end
echo.
pause
