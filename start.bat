@echo off
echo ====================================
echo TABLESYS - Start Script
echo University of Zambia
echo ====================================
echo.

echo Starting TABLESYS...
echo.

:: Check if backend virtual environment exists
if not exist "backend\venv\" (
    echo ERROR: Backend not set up. Please run setup.bat first!
    pause
    exit /b 1
)

:: Check if frontend node_modules exists
if not exist "frontend\node_modules\" (
    echo ERROR: Frontend not set up. Please run setup.bat first!
    pause
    exit /b 1
)

echo [1/2] Starting Backend Server...
start "TABLESYS Backend" cmd /k "cd backend && venv\Scripts\activate && uvicorn app.main:app --reload"

:: Wait a moment for backend to start
timeout /t 5 /nobreak > nul

echo [2/2] Starting Frontend Server...
start "TABLESYS Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ====================================
echo TABLESYS is starting...
echo ====================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Login credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo Press Ctrl+C in each window to stop servers
echo Close this window when done
echo ====================================
echo.

pause
