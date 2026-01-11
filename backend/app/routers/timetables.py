from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
import asyncio
from ..database import get_db
from ..schemas import Timetable, TimetableCreate, TimetableWithSlots
from ..models import Timetable as TimetableModel, User
from ..auth import get_current_user, get_current_active_coordinator
from ..services.timetable_generator import TimetableGenerator

router = APIRouter(prefix="/api/timetables", tags=["timetables"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_progress(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

@router.get("/", response_model=List[Timetable])
async def get_timetables(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all timetables."""
    timetables = db.query(TimetableModel).offset(skip).limit(limit).all()
    return timetables

@router.get("/{timetable_id}", response_model=TimetableWithSlots)
async def get_timetable(
    timetable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific timetable with all slots."""
    timetable = db.query(TimetableModel).filter(TimetableModel.id == timetable_id).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    return timetable

@router.post("/", response_model=Timetable, status_code=status.HTTP_201_CREATED)
async def create_timetable(
    timetable: TimetableCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Create a new timetable (without generating slots). Coordinator only."""
    db_timetable = TimetableModel(**timetable.model_dump())
    db.add(db_timetable)
    db.commit()
    db.refresh(db_timetable)
    return db_timetable

@router.websocket("/generate/{timetable_id}")
async def generate_timetable_ws(
    websocket: WebSocket,
    timetable_id: int,
):
    """
    Generate timetable with real-time progress updates via WebSocket.
    This endpoint generates the timetable level by level (5th -> 4th -> 3rd -> 2nd).
    """
    await manager.connect(websocket)
    
    try:
        # Get database session
        db = next(get_db())
        
        # Check if timetable exists
        timetable = db.query(TimetableModel).filter(TimetableModel.id == timetable_id).first()
        
        if not timetable:
            await websocket.send_json({
                'status': 'error',
                'message': 'Timetable not found'
            })
            return
        
        # Progress callback function
        async def progress_callback(progress_data: dict):
            await manager.send_progress(progress_data, websocket)
        
        # Create generator instance
        generator = TimetableGenerator(
            db=db,
            timetable_id=timetable_id,
            progress_callback=lambda data: asyncio.create_task(progress_callback(data))
        )
        
        # Run generation
        await websocket.send_json({
            'status': 'started',
            'message': 'Timetable generation started'
        })
        
        success = generator.generate_timetable()
        
        if success:
            # Update timetable metadata
            timetable.generation_metadata = {
                'generated': True,
                'levels_processed': [5, 4, 3, 2]
            }
            db.commit()
            
            await websocket.send_json({
                'status': 'success',
                'message': 'Timetable generated successfully',
                'timetable_id': timetable_id
            })
        else:
            await websocket.send_json({
                'status': 'error',
                'message': 'Failed to generate timetable. Please check constraints.'
            })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await websocket.send_json({
            'status': 'error',
            'message': f'Error generating timetable: {str(e)}'
        })
    finally:
        if db:
            db.close()

@router.post("/{timetable_id}/activate", response_model=Timetable)
async def activate_timetable(
    timetable_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Activate a timetable (deactivate all others). Coordinator only."""
    timetable = db.query(TimetableModel).filter(TimetableModel.id == timetable_id).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    # Deactivate all other timetables
    db.query(TimetableModel).update({TimetableModel.is_active: False})
    
    # Activate this one
    timetable.is_active = True
    db.commit()
    db.refresh(timetable)
    
    return timetable

@router.delete("/{timetable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timetable(
    timetable_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db)
):
    """Delete a timetable. Coordinator only."""
    timetable = db.query(TimetableModel).filter(TimetableModel.id == timetable_id).first()
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    db.delete(timetable)
    db.commit()
    return None
