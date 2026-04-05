@echo off
echo.
echo ==========================================
echo   AI Brain - Setup Script
echo ==========================================
echo.

echo [1/3] Installing Python dependencies...
cd /d "%~dp0"
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/3] Creating vault folders...
mkdir "..\Memory\Projects"  2>nul
mkdir "..\Memory\Users"     2>nul
mkdir "..\Memory\Features"  2>nul
mkdir "..\Memory\Notes"     2>nul
echo Done.

echo.
echo [3/3] Checking AI backend...
echo.
echo =========================================
echo  FREE AI OPTIONS FOR YOUR GPU:
echo =========================================
echo.
echo  OPTION A (Recommended): Ollama (local, free, GPU)
echo    1. Download: https://ollama.com/download
echo    2. Run in terminal: ollama pull mistral
echo    3. That's it! Runs on your GPU automatically.
echo.
echo  OPTION B: Groq (free cloud, ultra fast)
echo    1. Sign up at: https://console.groq.com
echo    2. Get free API key
echo    3. Open ai_call.py and set GROQ_API_KEY
echo.
echo =========================================
echo.
echo Setup complete! Run the agent with:
echo   python main.py
echo.
pause
