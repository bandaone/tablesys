# TABLESYS Setup Guide

## Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- PostgreSQL 15 or higher
- Git (optional)

## Installation Steps

### Option 1: Using Setup Script (Windows)

1. Open Command Prompt as Administrator
2. Navigate to the TABLESYS directory:
   ```cmd
   cd c:\SYSTEMS\TABLESYS
   ```
3. Run the setup script:
   ```cmd
   setup.bat
   ```
4. Follow the on-screen instructions

### Option 2: Manual Setup

#### 1. Setup Database

```sql
-- Create database
CREATE DATABASE tablesys_db;

-- Create user
CREATE USER tablesys WITH PASSWORD 'tablesys123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE tablesys_db TO tablesys;
```

#### 2. Setup Backend

```cmd
cd backend

:: Create virtual environment
python -m venv venv

:: Activate virtual environment
venv\Scripts\activate

:: Install dependencies
pip install -r requirements.txt

:: Copy environment file
copy .env.example .env

:: Edit .env with your database credentials

:: Seed database
python seed_db.py

:: Run backend
uvicorn app.main:app --reload
```

The backend will be available at http://localhost:8000

#### 3. Setup Frontend

Open a new terminal:

```cmd
cd frontend

:: Install dependencies
npm install

:: Run frontend
npm run dev
```

The frontend will be available at http://localhost:3000

### Option 3: Using Docker

```cmd
:: Start all services
docker-compose up -d

:: View logs
docker-compose logs -f

:: Stop services
docker-compose down
```

## First-Time Login

1. Navigate to http://localhost:3000
2. Login with default credentials:
   - Username: `admin`
   - Password: `admin123`
3. **Important**: Change the default password immediately!

## Creating Additional Users

As a coordinator, you can create additional users:

1. Go to the Users page (coming soon)
2. Click "Add User"
3. Fill in the details and select the appropriate role:
   - **Coordinator**: Full system access
   - **HOD**: Department-specific access

## Importing Data

### Bulk Import Process

1. **Departments**: Create departments first (manual entry)
2. **Courses**: Go to Courses page → Bulk Upload
3. **Lecturers**: Go to Lecturers page → Bulk Upload
4. **Rooms**: Go to Rooms page → Bulk Upload
5. **Student Groups**: Go to Groups page → Bulk Upload

### Template Files

Download template files from each page's bulk upload dialog.

## Generating a Timetable

1. Navigate to the Timetables page
2. Click "Create Timetable"
3. Fill in the semester and year details
4. Click "Generate Timetable"
5. Watch the progress as it generates:
   - 5th Year (25%)
   - 4th Year (50%)
   - 3rd Year (75%)
   - 2nd Year (100%)

## Troubleshooting

### Backend won't start

- Check PostgreSQL is running
- Verify database credentials in `.env`
- Ensure port 8000 is not in use

### Frontend won't start

- Clear node_modules: `rd /s /q node_modules && npm install`
- Check port 3000 is not in use
- Verify backend is running

### Database connection errors

- Check PostgreSQL service is running
- Verify DATABASE_URL in `.env`
- Test connection: `psql -U tablesys -d tablesys_db`

### Timetable generation fails

- Ensure all required data is present:
  - Courses with assigned lecturers
  - Student groups assigned to courses
  - Sufficient rooms available
- Check for constraint conflicts
- Review backend logs for errors

## Development Tips

### Backend Development

```cmd
:: Run with auto-reload
uvicorn app.main:app --reload

:: View API docs
http://localhost:8000/docs

:: Check database
psql -U tablesys -d tablesys_db
```

### Frontend Development

```cmd
:: Run dev server
npm run dev

:: Build for production
npm run build

:: Preview production build
npm run preview
```

## System Requirements

### Minimum

- CPU: 2 cores
- RAM: 4 GB
- Storage: 10 GB

### Recommended

- CPU: 4 cores
- RAM: 8 GB
- Storage: 20 GB
- SSD for database

## Support

For issues and support, contact the development team.
