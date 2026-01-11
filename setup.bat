@echo off
echo ====================================
echo TABLESYS - Setup Script
echo University of Zambia
echo ====================================
echo.

echo [1/4] Setting up backend...
cd backend

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate

echo Installing backend dependencies...
pip install -r requirements.txt

echo Copying environment file...
if not exist .env (
    copy .env.example .env
    echo Created .env file - Please update with your database credentials
) else (
    echo .env file already exists
)

echo Seeding database...
python seed_db.py

echo.
echo [2/4] Setting up frontend...
cd ..\frontend

echo Installing frontend dependencies...
call npm install

echo.
echo [3/4] Setup complete!
echo.
echo ====================================
echo Next Steps:
echo ====================================
echo.
echo 1. Update backend\.env with your database credentials
echo 2. Ensure PostgreSQL is running
echo.
echo To start the application:
echo.
echo Backend:
echo   cd backend
echo   venv\Scripts\activate
echo   uvicorn app.main:app --reload
echo.
echo Frontend (in a new terminal):
echo   cd frontend
echo   npm run dev
echo.
echo Access the application at http://localhost:3000
echo API documentation at http://localhost:8000/docs
echo.
echo Default login:
echo   Username: admin
echo   Password: admin123
echo.
echo ====================================

pause
