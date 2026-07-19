from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_active_lab_coordinator, get_current_user
from ..database import get_db
from ..models import ActivityType as ActivityTypeModel, User
from ..schemas import ActivityType, ActivityTypeCreate, ActivityTypeUpdate
from ..utils.sanitization import sanitize_input


router = APIRouter(prefix="/api/v1/activity-types", tags=["activity-types"])


def _tenant_id(current_user: User) -> int:
    if current_user.university_id is None:
        raise HTTPException(status_code=403, detail="Tenant-scoped access required")
    return current_user.university_id


@router.get("/", response_model=List[ActivityType])
async def list_activity_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = _tenant_id(current_user)
    return (
        db.query(ActivityTypeModel)
        .filter(ActivityTypeModel.university_id == tenant_id)
        .order_by(ActivityTypeModel.display_name.asc())
        .all()
    )


@router.post("/", response_model=ActivityType, status_code=status.HTTP_201_CREATED)
async def create_activity_type(
    payload: ActivityTypeCreate,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db),
):
    tenant_id = _tenant_id(current_user)
    key = sanitize_input(payload.key.lower(), max_length=50)
    existing = (
        db.query(ActivityTypeModel)
        .filter(ActivityTypeModel.university_id == tenant_id, ActivityTypeModel.key == key)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Activity type '{key}' already exists")

    row = ActivityTypeModel(
        university_id=tenant_id,
        key=key,
        display_name=sanitize_input(payload.display_name, max_length=100),
        color=payload.color,
        default_duration_periods=payload.default_duration_periods,
        default_frequency_per_week=payload.default_frequency_per_week,
        requires_subgroups=payload.requires_subgroups,
        resource_tags_required=payload.resource_tags_required,
        counts_toward_contact_hours=payload.counts_toward_contact_hours,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{activity_type_id}", response_model=ActivityType)
async def update_activity_type(
    activity_type_id: int,
    payload: ActivityTypeUpdate,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db),
):
    tenant_id = _tenant_id(current_user)
    row = (
        db.query(ActivityTypeModel)
        .filter(ActivityTypeModel.id == activity_type_id, ActivityTypeModel.university_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Activity type not found")

    data = payload.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"] is not None:
        data["display_name"] = sanitize_input(data["display_name"], max_length=100)
    for field, value in data.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{activity_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity_type(
    activity_type_id: int,
    current_user: User = Depends(get_current_active_lab_coordinator),
    db: Session = Depends(get_db),
):
    tenant_id = _tenant_id(current_user)
    row = (
        db.query(ActivityTypeModel)
        .filter(ActivityTypeModel.id == activity_type_id, ActivityTypeModel.university_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Activity type not found")
    db.delete(row)
    db.commit()
    return None
