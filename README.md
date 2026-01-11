# TABLESYS - University Timetable Management System

A professional timetable generation and management system for the University of Zambia.

## 🚀 Features

- **Automated Timetable Generation**: Level-based algorithm (5th → 4th → 3rd → 2nd years)
- **Real-Time Progress Tracking**: WebSocket updates with percentages and status comments
- **Role-Based Access Control**: Separate privileges for Coordinators and HODs
- **Simple Authentication**: Username-only login (no passwords required!)
- **Bulk Import Management**: Context-specific bulk uploads on respective pages
- **University of Zambia Branding**: Professional UNZA color scheme
- **Constraint Optimization**: OR-Tools CP-SAT solver for optimal scheduling
- **Docker Ready**: Fully containerized deployment

## 🐳 Quick Start with Docker (Recommended)

**The easiest way to run TABLESYS:**

```bash
cd c:\SYSTEMS\TABLESYS
docker-compose up -d
```

Then open http://localhost:3000 and login with just a username:
- **coordinator** or **admin** (full access)
- **MEC**, **CS**, **MATH**, **ELE**, **CIV**, **PHY**, **CHEM**, **BIO** (HOD access)

📖 **See [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for complete Docker documentation**

## 💻 Manual Setup (Alternative)

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env

# Update .env with your database credentials

# Run the application
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

## User Roles

### Coordinator
- Full system access
- Can manage all courses, lecturers, rooms, and groups
- Can generate and manage complete timetables
- Can bulk import any entity
- Can assign HODs to departments

### Head of Department (HOD)
- Department-specific access
- Can view and manage courses in their department
- Can view assigned lecturers
- Can view generated timetables for their department
- Can bulk import courses for their department only

## Technology Stack

- **Backend:**
  - FastAPI
  - PostgreSQL
  - SQLAlchemy
  - OR-Tools
  - Python-Jose (JWT)
  - Pandas

- **Frontend:**
  - React 18
  - TypeScript
  - Material-UI (MUI)
  - React Router
  - Axios

- **DevOps:**
  - Docker
  - Docker Compose

## API Documentation

Once the backend is running, access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Timetable Generation Algorithm

The system uses a sophisticated level-based approach:

1. **5th Year Generation**: Creates schedule for final year students first
2. **4th Year Generation**: Adds 4th year schedule, avoiding conflicts
3. **3rd Year Generation**: Continues with 3rd year students
4. **2nd Year Generation**: Completes with 2nd year students
5. **Consolidation**: Combines all levels into final timetable

Each level's generation:
- Uses CP-SAT solver from OR-Tools
- Respects lecturer availability
- Avoids room conflicts
- Ensures proper course hour allocation
- Updates progress in real-time via WebSocket

## Bulk Upload Format

### Courses CSV/Excel Format
```
code,name,department_id,level,credits,lecture_hours,tutorial_hours,practical_hours
CS101,Introduction to Programming,1,2,3,3,1,2
MATH201,Calculus II,2,3,4,4,2,0
```

### Lecturers CSV/Excel Format
```
staff_number,full_name,email,department_id,max_hours_per_week
L001,Dr. John Doe,j.doe@unza.zm,1,20
L002,Prof. Jane Smith,j.smith@unza.zm,2,18
```

### Rooms CSV/Excel Format
```
name,building,capacity,room_type,has_projector,has_computers
R101,Main Building,50,lecture,true,false
LAB1,Computer Science,30,lab,true,true
```

### Student Groups CSV/Excel Format
```
name,level,department_id,size
CS-5A,5,1,45
MATH-4B,4,2,38
```

## Development

### Backend Development

```bash
cd backend

# Run tests (when implemented)
pytest

# Check code style
black app/
flake8 app/

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Frontend Development

```bash
cd frontend

# Type checking
npm run tsc

# Linting
npm run lint

# Build for production
npm run build
```

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql://tablesys:tablesys123@localhost:5432/tablesys_db
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Color Scheme (UNZA Brand)

- **Primary (Dark Blue)**: #003366
- **Secondary (Orange/Gold)**: #FF8C00
- **Accent (Light Blue)**: #4A90E2

## License

Proprietary - University of Zambia

## Support

For issues and questions, contact the development team.

---

Built with ❤️ for the University of Zambia
