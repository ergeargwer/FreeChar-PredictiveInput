@echo off
echo ===================================================
echo     FreeChar AI Input Method Desktop Launcher
echo ===================================================
echo.
echo Installing/Checking dependencies (pygame, jieba)...

:: Try using the "py" launcher first (recommened for multiple Python environments)
py -m pip install pygame jieba --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org >nul 2>nul
if %errorlevel% neq 0 (
    pip install pygame jieba --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
)

echo.
echo Generating sound effects...
py sound_generator.py >nul 2>nul
if %errorlevel% neq 0 (
    python sound_generator.py
)

echo.
echo Launching Pygame UI...
py main.py
if %errorlevel% neq 0 (
    echo.
    echo Fallback: Launching with standard python...
    python main.py
)

if %errorlevel% neq 0 (
    echo.
    echo Failed to start. Please check your Python installations.
    pause
)
