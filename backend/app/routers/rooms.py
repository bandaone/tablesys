# OWNER: Antigravity | TASK: Resource Management | DATE: 2026-03-01
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io
from ..database import get_db
from ..schemas import Room, RoomCreate, RoomUpdate
from ..models import UserRole, Room as RoomModel, User, Department, University
from ..auth import get_current_user, get_current_active_coordinator
from ..utils.sanitization import sanitize_input
from ..utils.audit_logger import AuditLogger
from ..services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rooms", tags=["rooms"])

# ---------------------------------------------------------------------------
# Accepted values
# ---------------------------------------------------------------------------

VALID_ROOM_TYPES = {
    "lecture_hall", "tutorial_room", "seminar_room",
    "lab", "drawing_room", "surveying_room", "auditorium",
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_room_fields(name: str, capacity: int, room_type: str) -> Optional[dict]:
    """Validate room field values. Returns error dict if invalid, None if valid."""
    if not name or not name.strip():
        return {"detail": "Room name cannot be empty", "field": "name"}
    if len(name) > 100:
        return {"detail": "Room name must be 100 characters or less", "field": "name"}
    if not (1 <= capacity <= 1000):
        return {"detail": "Capacity must be between 1 and 1000", "field": "capacity"}
    if room_type not in VALID_ROOM_TYPES:
        return {
            "detail": f"Invalid room type '{room_type}'. Must be one of: {', '.join(sorted(VALID_ROOM_TYPES))}",
            "field": "room_type",
        }
    return None


def resolve_university_id(db: Session, current_user: User) -> int:
    if getattr(current_user, "university_id", None):
        return current_user.university_id
    uni = db.query(University).order_by(University.id.asc()).first()
    if not uni:
        raise HTTPException(status_code=500, detail="No university found for room creation")
    return uni.id


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[Room])
async def get_rooms(
    skip: int = 0,
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all rooms. HODs see only their department + unrestricted rooms."""
    query = db.query(RoomModel)
    if current_user.role == UserRole.HOD and current_user.department_id:
        query = query.filter(
            (RoomModel.department_id == None) |
            (RoomModel.department_id == current_user.department_id)
        )
    rooms = query.order_by(RoomModel.priority_level.desc(), RoomModel.name).offset(skip).limit(limit).all()
    return rooms


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------

@router.post("/", response_model=Room, status_code=status.HTTP_201_CREATED)
async def create_room(
    request: Request,
    room: RoomCreate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """Create a new room. Coordinator only."""
    err = validate_room_fields(room.name, room.capacity, room.room_type)
    if err:
        raise HTTPException(status_code=422, detail=err["detail"])

    if room.department_id:
        if not db.query(Department).filter(Department.id == room.department_id).first():
            raise HTTPException(status_code=422, detail="Invalid department_id")

    if db.query(RoomModel).filter(RoomModel.name == room.name).first():
        raise HTTPException(status_code=409, detail=f"Room '{room.name}' already exists")

    room_data = room.model_dump()
    # Backward compatibility: legacy model versions do not expose text availability.
    room_data.pop("availability", None)
    room_data["university_id"] = resolve_university_id(db, current_user)
    room_data["name"] = sanitize_input(room.name, max_length=100)
    room_data["building"] = sanitize_input(room.building, max_length=100)

    db_room = RoomModel(**room_data)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="CREATE",
        resource_type="room",
        resource_id=db_room.id,
        details={"room_name": db_room.name, "capacity": db_room.capacity}
    )
    NotificationService(db).notify_coordinators(
        title="New Room Added",
        message=f"{current_user.username} has added room {db_room.name} (Capacity: {db_room.capacity}).",
        type="info"
    )
    
    return db_room


# ---------------------------------------------------------------------------
# PUT /{room_id}
# ---------------------------------------------------------------------------

@router.put("/{room_id}", response_model=Room)
async def update_room(
    request: Request,
    room_id: int,
    room_update: RoomUpdate,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """Update a room. Coordinator only."""
    db_room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    update_data = room_update.model_dump(exclude_unset=True)
    # Backward compatibility: ignore removed text availability field on ORM writes.
    update_data.pop("availability", None)

    # Validate merged state
    merged_name     = update_data.get("name",      db_room.name)
    merged_capacity = update_data.get("capacity",  db_room.capacity)
    merged_type     = update_data.get("room_type", db_room.room_type)
    err = validate_room_fields(merged_name, merged_capacity, merged_type)
    if err:
        raise HTTPException(status_code=422, detail=err["detail"])

    if "department_id" in update_data and update_data["department_id"]:
        if not db.query(Department).filter(Department.id == update_data["department_id"]).first():
            raise HTTPException(status_code=422, detail="Invalid department_id")

    if "name" in update_data:
        update_data["name"] = sanitize_input(update_data["name"], max_length=100)

    for field, value in update_data.items():
        setattr(db_room, field, value)

    db.commit()
    db.refresh(db_room)
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="UPDATE",
        resource_type="room",
        resource_id=db_room.id,
        details={"room_name": db_room.name, "updates": list(update_data.keys())}
    )
    
    return db_room


# ---------------------------------------------------------------------------
# PATCH /{room_id}/block  (quick toggle — no full form needed)
# ---------------------------------------------------------------------------

@router.patch("/{room_id}/block", response_model=Room)
async def toggle_room_block(
    request: Request,
    room_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """Toggle the is_blocked flag on a room. Coordinator only."""
    db_room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    db_room.is_blocked = not db_room.is_blocked
    db.commit()
    db.refresh(db_room)
    
    action = "BLOCKED" if db_room.is_blocked else "UNBLOCKED"
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation=action,
        resource_type="room",
        resource_id=db_room.id,
        details={"room_name": db_room.name}
    )
    NotificationService(db).notify_coordinators(
        title=f"Room {action.capitalize()}",
        message=f"Room {db_room.name} was {action.lower()} by {current_user.username}.",
        type="warning" if db_room.is_blocked else "info"
    )
    
    return db_room


# ---------------------------------------------------------------------------
# DELETE /{room_id}
# ---------------------------------------------------------------------------

@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    request: Request,
    room_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """Delete a room. Coordinator only."""
    db_room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    db.delete(db_room)
    db.commit()
    
    name = db_room.name
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="room",
        resource_id=room_id,
        details={"room_name": name}
    )
    NotificationService(db).notify_coordinators(
        title="Room Deleted",
        message=f"Room {name} was deleted by {current_user.username}.",
        type="warning"
    )
    
    return None


# ---------------------------------------------------------------------------
# DELETE /   (clear all)
# ---------------------------------------------------------------------------

@router.delete("/", status_code=status.HTTP_200_OK)
async def delete_all_rooms(
    request: Request,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """Delete all rooms. Coordinator only. Use before bulk re-upload."""
    count = db.query(RoomModel).count()
    db.query(RoomModel).delete()
    db.commit()
    
    AuditLogger.log_data_modification(
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        operation="DELETE",
        resource_type="room_bulk",
        details={"count_deleted": count}
    )
    NotificationService(db).notify_coordinators(
        title="All Rooms Cleared",
        message=f"A bulk clear of all {count} rooms was executed by {current_user.username}.",
        type="warning"
    )
    
    return {"status": "success", "deleted": count, "message": f"Deleted {count} rooms"}


# ---------------------------------------------------------------------------
# POST /bulk-upload
# ---------------------------------------------------------------------------

# Furniture-type → room_type mapping used during CSV / Excel import
_FURNITURE_TO_TYPE = {
    "lab":               "lab",
    "laboratory":        "lab",
    "computer lab":      "lab",
    "drawing":           "drawing_room",
    "drawing room":      "drawing_room",
    "surveying":         "surveying_room",
    "seminar":           "seminar_room",
    "tutorial":          "tutorial_room",
    "auditorium":        "auditorium",
    "lecture theatre":   "lecture_hall",
    "lecture hall":      "lecture_hall",
    "classroom":         "lecture_hall",
    "workshop":          "lab",
}

# Column aliases → canonical internal name (keys are lower-cased column headers)
_COL_ALIASES = {
    # identity / code
    "code":             "code",
    "room code":        "code",
    "venue code":       "code",
    # name
    "name":             "name",
    "room name":        "name",
    "venue name":       "name",
    "venue":            "name",
    # building
    "building":         "building",
    "block":            "building",
    # furniture / type
    "furniture type":   "furniture_type",
    "furniture":        "furniture_type",
    "room type":        "room_type",
    "type":             "furniture_type",
    # equipment
    "equipment":        "equipment",
    "equipment list":   "equipment",
    # capacity
    "capacity":         "capacity",
    "size":             "capacity",
    "seats":            "capacity",
    # availability
    "availability":     "availability",
    "available":        "availability",
    # priority
    "priority":         "priority_level",
    "priority level":   "priority_level",
    "priority_level":   "priority_level",
}


def _infer_room_type(furniture_raw: str) -> str:
    """Map a free-text furniture_type value to a canonical room_type."""
    lower = str(furniture_raw).strip().lower()
    for keyword, rt in _FURNITURE_TO_TYPE.items():
        if keyword in lower:
            return rt
    return "lecture_hall"  # safe default


def _parse_equipment(equipment_raw: str) -> dict:
    """
    Parse a free-text equipment string into boolean flags.
    e.g. 'Projector, Whiteboard' -> has_projector=True, has_whiteboard=True
    """
    s = str(equipment_raw).strip().lower()
    return {
        "has_projector":  any(k in s for k in ("projector", "lcd", "smartboard")),
        "has_whiteboard": "whiteboard" in s or "white board" in s,
        "has_chalkboard": any(k in s for k in ("chalkboard", "chalk board", "blackboard")),
    }


@router.post("/bulk-upload", response_model=dict)
async def bulk_upload_rooms(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """
    Bulk upload rooms / venues from CSV or Excel.

    Accepts the school's standard venues format:
        Code | Name | Building | Furniture Type | Equipment | Capacity | Availability | Priority

    Also accepts the legacy format:
        name | capacity | building | room_type | furniture_type | ...

    Columns are matched case-insensitively via aliases.
    Rows are upserted: existing rooms matched by Code or Name are updated.
    Semicolon-separated CSVs (common in Excel exports) are auto-detected.
    """
    ALLOWED_CONTENT_TYPES = {
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")

    try:
        contents = await file.read()

        if file.content_type == "text/csv":
            text = contents.decode("utf-8", errors="replace")
            if "\t" in text and text.count("\t") > text.count(","):
                sep = "\t"
            else:
                sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep)
        else:
            df = pd.read_excel(io.BytesIO(contents))
        # Normalise columns and apply aliases
        df.columns = [c.strip().lower() for c in df.columns]
        rename_map = {col: _COL_ALIASES[col] for col in df.columns if col in _COL_ALIASES}
        df = df.rename(columns=rename_map)
        df = df.loc[:, ~df.columns.duplicated()]  # drop duplicate targets

        # Need at least a name or code column
        if "name" not in df.columns and "code" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Cannot find a room name or code column. Expected: Name, Code, Venue, or Venue Code."
            )
        if "capacity" not in df.columns:
            raise HTTPException(status_code=400, detail="Missing required column: Capacity")

        # Ensure both name and code exist
        if "name" not in df.columns:
            df["name"] = df["code"]
        if "code" not in df.columns:
            df["code"] = df["name"]

        created_count = updated_count = skipped_count = 0
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                row_name = str(row.get("name", "")).strip()
                row_code = str(row.get("code", row_name)).strip()
                if not row_name:
                    row_name = row_code
                if not row_name:
                    skipped_count += 1
                    continue

                # Room type
                if "room_type" in df.columns and pd.notna(row.get("room_type")):
                    raw_type = str(row["room_type"]).strip().lower()
                    room_type = raw_type if raw_type in VALID_ROOM_TYPES else _infer_room_type(raw_type)
                elif "furniture_type" in df.columns and pd.notna(row.get("furniture_type")):
                    room_type = _infer_room_type(str(row["furniture_type"]))
                else:
                    room_type = "lecture_hall"

                # Equipment flags
                if "equipment" in df.columns and pd.notna(row.get("equipment")):
                    equip_flags = _parse_equipment(str(row["equipment"]))
                else:
                    def _bool_col(col: str, default: bool) -> bool:
                        if col not in df.columns or pd.isna(row.get(col)):
                            return default
                        return str(row[col]).strip().lower() in ("true", "1", "yes")
                    equip_flags = {
                        "has_whiteboard": _bool_col("has_whiteboard", True),
                        "has_chalkboard": _bool_col("has_chalkboard", False),
                        "has_projector":  _bool_col("has_projector", True),
                    }

                # Safe int parse helper
                def _safe_int(val, default: int) -> int:
                    try:
                        return max(1, int(float(str(val).replace(",", ""))))
                    except Exception:
                        return default

                room_data: dict = {
                    "university_id":  resolve_university_id(db, current_user),
                    "name":           sanitize_input(row_name, max_length=100),
                    "building":       sanitize_input(str(row.get("building", "")), max_length=100)
                                      if "building" in df.columns and pd.notna(row.get("building"))
                                      else "",
                    "capacity":       _safe_int(row["capacity"], 30),
                    "room_type":      room_type,
                    "priority_level": _safe_int(row["priority_level"], 5)
                                      if "priority_level" in df.columns and pd.notna(row.get("priority_level"))
                                      else 5,
                    "is_blocked":     False,
                    **equip_flags,
                }

                # Upsert: match by code (stored as name = code) or name
                existing = (
                    db.query(RoomModel).filter(RoomModel.name == row_code).first()
                    or db.query(RoomModel).filter(RoomModel.name == row_name).first()
                )
                if existing:
                    for key, value in room_data.items():
                        setattr(existing, key, value)
                    updated_count += 1
                else:
                    db.add(RoomModel(**room_data))
                    created_count += 1

            except Exception as exc:
                errors.append(f"Row {idx + 2}: {exc}")
                skipped_count += 1

        db.commit()
        return {
            "status":  "success",
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "errors":  errors or None,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Room bulk upload error: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail="Could not process the uploaded file. Please check the format and try again.")
