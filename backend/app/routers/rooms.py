from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
from ..database import get_db
from ..schemas import Room, RoomCreate, RoomUpdate
from ..models import Room as RoomModel, User
from ..auth import get_current_user, get_current_active_coordinator

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

@router.get("/", response_model=List[Room])
async def get_rooms(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all rooms."""
    rooms = db.query(RoomModel).offset(skip).limit(limit).all()
    return rooms

@router.post("/", response_model=Room, status_code=status.HTTP_201_CREATED)
async def create_room(
    room: RoomCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Create a new room. Coordinator only."""
    existing = db.query(RoomModel).filter(RoomModel.name == room.name).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Room already exists")
    
    db_room = RoomModel(**room.model_dump())
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room

@router.put("/{room_id}", response_model=Room)
async def update_room(
    room_id: int,
    room_update: RoomUpdate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Update a room. Coordinator only."""
    db_room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    update_data = room_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_room, field, value)
    
    db.commit()
    db.refresh(db_room)
    return db_room

@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete a room. Coordinator only."""
    db_room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    db.delete(db_room)
    db.commit()
    return None

@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_rooms(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """
    Bulk upload rooms from Excel/CSV file. Coordinator only.
    Expected columns: name, building, capacity, room_type, has_projector, has_computers
    """
    if file.content_type not in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")
    
    try:
        contents = await file.read()
        
        if file.content_type == "text/csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        required_columns = ['name', 'building', 'capacity', 'room_type']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        if 'has_projector' not in df.columns:
            df['has_projector'] = True
        if 'has_computers' not in df.columns:
            df['has_computers'] = False
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                existing = db.query(RoomModel).filter(RoomModel.name == str(row['name'])).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                room = RoomModel(
                    name=str(row['name']),
                    building=str(row['building']),
                    capacity=int(row['capacity']),
                    room_type=str(row['room_type']),
                    has_projector=bool(row.get('has_projector', True)),
                    has_computers=bool(row.get('has_computers', False))
                )
                
                db.add(room)
                created_count += 1
                
            except Exception as e:
                errors.append(f"Row {idx + 2}: {str(e)}")
                skipped_count += 1
        
        db.commit()
        
        return {
            "status": "success",
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")
