# TABLESYS - Quick Reference

## 🎯 Project Overview

TABLESYS is a complete university timetable management system built from scratch with:
- ✅ Level-based timetable generation (5th → 4th → 3rd → 2nd years)
- ✅ Real-time progress tracking with WebSocket
- ✅ Role-based access control (Coordinator & HOD)
- ✅ Bulk upload on respective pages
- ✅ University of Zambia color theme

## 📁 Project Structure

```
TABLESYS/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── models/            # Database models
│   │   ├── routers/           # API endpoints
│   │   ├── services/          # Business logic (timetable generator)
│   │   ├── auth.py            # Authentication
│   │   ├── config.py          # Configuration
│   │   ├── database.py        # Database connection
│   │   ├── schemas.py         # Pydantic schemas
│   │   └── main.py            # FastAPI app
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── seed_db.py            # Database seeding script
│   └── .env.example
│
├── frontend/                  # React + TypeScript frontend
│   ├── src/
│   │   ├── components/       # Reusable components
│   │   │   └── DashboardLayout.tsx
│   │   ├── contexts/         # React contexts
│   │   │   └── AuthContext.tsx
│   │   ├── pages/            # Page components
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── CoursesPage.tsx
│   │   │   └── TimetablesPage.tsx
│   │   ├── api.ts            # API service layer
│   │   ├── theme.ts          # MUI theme (UNZA colors)
│   │   ├── App.tsx           # Main app component
│   │   └── main.tsx          # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docker-compose.yml        # Docker orchestration
├── README.md                 # Main documentation
├── SETUP_GUIDE.md           # Detailed setup instructions
├── setup.bat                # Windows setup script
└── .gitignore

```

## 🚀 Quick Start Commands

### Using Docker (Easiest)
```bash
cd c:\SYSTEMS\TABLESYS
docker-compose up -d
# Access: http://localhost:3000
```

### Manual Start
```bash
# Terminal 1 - Backend
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## 🎨 UNZA Color Theme

The system uses University of Zambia's official colors:
- **Primary (Dark Blue)**: `#003366`
- **Secondary (Orange/Gold)**: `#FF8C00`
- **Accent (Light Blue)**: `#4A90E2`

## 🔑 Default Credentials

```
Username: admin
Password: value from TABLESYS_INITIAL_USER_PASSWORD in .env
```
**⚠️ Rotate immediately after first login.**

## 📊 Key Features

### 1. Level-Based Timetable Generation
- Generates progressively: 5th → 4th → 3rd → 2nd years
- Uses OR-Tools CP-SAT solver
- Real-time WebSocket progress updates
- Shows percentage and status messages

### 2. Role-Based Access Control

**Coordinator:**
- Full system access
- Manage all entities (courses, lecturers, rooms, groups)
- Generate timetables
- Bulk upload any data

**HOD (Head of Department):**
- Department-specific access
- View/manage own department's courses
- View assigned lecturers
- Bulk upload courses for own department only

### 3. Bulk Upload Functionality
- **Courses**: Upload from Courses page
- **Lecturers**: Upload from Lecturers page
- **Rooms**: Upload from Rooms page
- **Groups**: Upload from Groups page
- Supports CSV and Excel formats
- Download templates from each page

## 🔄 Timetable Generation Process

1. **Create Timetable** → Enter name, semester, year
2. **Start Generation** → Click "Generate Timetable"
3. **Watch Progress**:
   - 0-25%: Generating 5th year
   - 25-50%: Generating 4th year
   - 50-75%: Generating 3rd year
   - 75-100%: Generating 2nd year
4. **Complete** → View combined timetable

## 📝 Bulk Upload Templates

### Courses Template (CSV)
```csv
code,name,department_id,level,credits,lecture_hours,tutorial_hours,practical_hours
CS101,Intro to Programming,1,2,3,3,1,2
```

### Lecturers Template (CSV)
```csv
staff_number,full_name,email,department_id,max_hours_per_week
L001,Dr. John Doe,j.doe@unza.zm,1,20
```

### Rooms Template (CSV)
```csv
name,building,capacity,room_type,has_projector,has_computers
R101,Main Building,50,lecture,true,false
```

### Groups Template (CSV)
```csv
name,level,department_id,size
CS-5A,5,1,45
```

## 🛠️ Development

### Backend Routes
```
POST   /api/auth/login         - User authentication
GET    /api/courses/           - List courses (filtered by role)
POST   /api/courses/bulk-upload - Bulk upload courses
GET    /api/lecturers/         - List lecturers
POST   /api/rooms/             - Create room
GET    /api/timetables/        - List timetables
WS     /api/timetables/generate/{id} - Generate with progress
```

### Frontend Routes
```
/login              - Login page
/dashboard          - Dashboard overview
/courses            - Courses management
/lecturers          - Lecturers management
/rooms              - Rooms management
/groups             - Student groups management
/timetables         - Timetable generation
/departments        - Departments management
```

## 🔧 Configuration

### Backend Environment (.env)
```env
DATABASE_URL=postgresql://tablesys:<32+_char_db_password>@localhost:5432/tablesys_db
SECRET_KEY=<64_char_random_hex_secret>
TABLESYS_INITIAL_USER_PASSWORD=<24+_char_bootstrap_user_password>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Frontend Configuration (vite.config.ts)
```typescript
server: {
  port: 3000,
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```

## 📦 Key Dependencies

### Backend
- FastAPI - Web framework
- SQLAlchemy - ORM
- OR-Tools - Constraint programming
- Python-Jose - JWT authentication
- Pandas - Data processing

### Frontend
- React 18 - UI framework
- Material-UI - Component library
- TypeScript - Type safety
- Axios - HTTP client
- React Router - Navigation

## 🐛 Common Issues & Solutions

### Backend won't start
```bash
# Check PostgreSQL is running
# Verify .env file exists and has correct credentials
# Port 8000 not in use
```

### Frontend won't start
```bash
cd frontend
rd /s /q node_modules
npm install
npm run dev
```

### Database connection error
```bash
# Check PostgreSQL service
# Verify database exists: psql -U tablesys -d tablesys_db
# Re-run seed_db.py
```

### Timetable generation fails
- Ensure courses have assigned lecturers
- Verify student groups are assigned to courses
- Check sufficient rooms are available
- Review constraint conflicts in logs

## 📚 Documentation

- **README.md** - Project overview and quick start
- **SETUP_GUIDE.md** - Detailed installation guide
- **API Docs** - http://localhost:8000/docs (Swagger UI)

## 🎓 Workflow Example

1. **Setup System**
   - Run setup.bat
   - Login as admin

2. **Add Data**
   - Create departments (manual)
   - Bulk upload courses
   - Bulk upload lecturers
   - Bulk upload rooms
   - Bulk upload student groups

3. **Assign Resources**
   - Assign lecturers to courses
   - Assign groups to courses

4. **Generate Timetable**
   - Create new timetable
   - Click "Generate"
   - Watch real-time progress
   - Activate when complete

5. **View & Export**
   - View generated timetable
   - Export if needed
   - Share with departments

## 🚀 Production Deployment

1. Update environment variables
2. Change SECRET_KEY
3. Use production database
4. Enable HTTPS
5. Configure CORS properly
6. Set up backups
7. Monitor logs

## 📞 Support

For issues or questions, contact the development team.

---

**Built for the University of Zambia** 🇿🇲
Version 1.0.0 | January 2026
