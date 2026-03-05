@echo off
REM WiFi CSI Presence Detection - Windows Setup Script

echo ================================================
echo   WiFi CSI Presence Detection - Setup
echo ================================================
echo.

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    Error: Python not found. Please install Python 3.7 or later.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo    Found: %PYTHON_VERSION%

REM Navigate to script directory
cd /d "%~dp0"
set PYTHON_DIR=%cd%\python

if not exist "%PYTHON_DIR%" (
    echo Error: Python directory not found
    pause
    exit /b 1
)

cd "%PYTHON_DIR%"

REM Check if virtual environment exists
if not exist "env" (
    echo.
    echo Creating virtual environment...
    python -m venv env
    echo    Virtual environment created
) else (
    echo.
    echo Virtual environment already exists
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call env\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
echo    pip upgraded

REM Install requirements
echo.
echo Installing Python dependencies...
if exist "..\requirements.txt" (
    pip install -r ..\requirements.txt
    echo    Dependencies installed
) else (
    echo    Warning: requirements.txt not found, installing manually...
    pip install numpy scipy matplotlib pyserial
    echo    Dependencies installed
)

echo.
echo ================================================
echo   Setup Complete!
echo ================================================
echo.
echo Next Steps:
echo.
echo   1. Configure WiFi in firmware\csi_receiver\main\csi_receiver.c
echo      (Change WIFI_SSID and WIFI_PASS)
echo.
echo   2. Flash ESP32 firmware (if not already done)
echo.
echo   3. Run presence detection:
echo      cd python
echo      env\Scripts\activate.bat
echo      python run_presence_detection.py
echo.
echo ================================================
echo.
pause
