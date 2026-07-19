from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List

from ..auth import get_current_user, get_current_active_tenant_admin, is_tenant_admin
from ..database import get_db
from ..models import School as SchoolModel, User
from ..schemas import (
    School,
    SchoolCreate,
    SchoolProfileUploadApplyRequest,
    SchoolProfileUploadApplyResponse,
    SchoolProfileUploadPreviewResponse,
    SchoolUpdate,
)
from ..services.school_profile_import import SchoolProfileImportService
from ..utils.sanitization import sanitize_input


router = APIRouter(prefix="/api/v1/schools", tags=["schools"])


def _school_query_for_user(db: Session, user: User):
    query = db.query(SchoolModel)
    if getattr(user, "university_id", None):
        query = query.filter(SchoolModel.university_id == user.university_id)
    if is_tenant_admin(user):
        return query
    if getattr(user, "school_id", None) is not None:
        return query.filter(SchoolModel.id == user.school_id)
    return query


def _tenant_school_or_404(db: Session, school_id: int, current_user: User) -> SchoolModel:
    school = db.query(SchoolModel).filter(
        SchoolModel.id == school_id,
        SchoolModel.university_id == current_user.university_id,
    ).first()
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return school


@router.get("/", response_model=List[School])
async def get_schools(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _school_query_for_user(db, current_user).order_by(SchoolModel.name.asc()).all()


@router.post("/", response_model=School, status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreate,
    current_user: User = Depends(get_current_active_tenant_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(SchoolModel).filter(
        SchoolModel.university_id == current_user.university_id,
        ((SchoolModel.name == payload.name) | (SchoolModel.code == payload.code)),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A school with that name or code already exists")

    row = SchoolModel(
        university_id=current_user.university_id,
        name=sanitize_input(payload.name, max_length=200),
        code=sanitize_input(payload.code, max_length=20),
        description=sanitize_input(payload.description, max_length=500) if payload.description else None,
        academic_calendar_id=payload.academic_calendar_id,
        scheduling_policy=payload.scheduling_policy,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{school_id}", response_model=School)
async def update_school(
    school_id: int,
    payload: SchoolUpdate,
    current_user: User = Depends(get_current_active_tenant_admin),
    db: Session = Depends(get_db),
):
    row = db.query(SchoolModel).filter(
        SchoolModel.id == school_id,
        SchoolModel.university_id == current_user.university_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="School not found")

    if payload.name is not None:
        row.name = sanitize_input(payload.name, max_length=200)
    if payload.code is not None:
        row.code = sanitize_input(payload.code, max_length=20)
    if payload.description is not None:
        row.description = sanitize_input(payload.description, max_length=500)
    if payload.academic_calendar_id is not None:
        row.academic_calendar_id = payload.academic_calendar_id
    if payload.scheduling_policy is not None:
        row.scheduling_policy = payload.scheduling_policy
    if payload.is_active is not None:
        row.is_active = payload.is_active

    db.commit()
    db.refresh(row)
    return row


@router.delete("/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_school(
    school_id: int,
    current_user: User = Depends(get_current_active_tenant_admin),
    db: Session = Depends(get_db),
):
    row = db.query(SchoolModel).filter(
        SchoolModel.id == school_id,
        SchoolModel.university_id == current_user.university_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="School not found")
    db.delete(row)
    db.commit()
    return None


@router.post("/{school_id}/profile-upload/preview", response_model=SchoolProfileUploadPreviewResponse)
async def preview_school_profile_upload(
    school_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_tenant_admin),
    db: Session = Depends(get_db),
):
    school = _tenant_school_or_404(db, school_id, current_user)
    contents = await file.read()
    service = SchoolProfileImportService(db, current_user, school)
    return service.build_preview(contents=contents, content_type=file.content_type or "")


@router.post("/{school_id}/profile-upload/apply", response_model=SchoolProfileUploadApplyResponse)
async def apply_school_profile_upload(
    school_id: int,
    payload: SchoolProfileUploadApplyRequest,
    current_user: User = Depends(get_current_active_tenant_admin),
    db: Session = Depends(get_db),
):
    school = _tenant_school_or_404(db, school_id, current_user)
    service = SchoolProfileImportService(db, current_user, school)
    return service.apply_preview(payload)
