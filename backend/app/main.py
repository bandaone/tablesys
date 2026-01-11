from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import auth, courses, lecturers, rooms, groups, departments, timetables

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TABLESYS - University Timetable Management System",
    description="Professional timetable generation and management system for the University of Zambia",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(departments.router)
app.include_router(courses.router)
app.include_router(lecturers.router)
app.include_router(rooms.router)
app.include_router(groups.router)
app.include_router(timetables.router)

@app.get("/")
async def root():
    return {
        "message": "TABLESYS API - University of Zambia Timetable Management System",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
