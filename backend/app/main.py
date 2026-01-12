from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import auth, courses, lecturers, rooms, groups, departments, timetables
import os

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TABLESYS - University Timetable Management System",
    description="Professional timetable generation and management system for the University of Zambia",
    version="1.0.0"
)

# Configure CORS with environment-based origins
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]

# Add production origin if set
if frontend_url := os.getenv("FRONTEND_URL"):
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
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
