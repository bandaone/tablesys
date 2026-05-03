"""
Template Profile Routes
=======================
Endpoints for uploading structural timetable templates (Word/Excel),
previewing the parsed layout, and saving a school's TemplateProfile.

Flow:
  POST /api/templates/upload-preview  → Parse file, return containers for UI review
  POST /api/templates/save            → Save confirmed containers as TemplateProfile
  GET  /api/templates/                → List all saved profiles
  GET  /api/templates/{id}            → Get a single profile
  PUT  /api/templates/{id}/activate   → Set as active profile
  DELETE /api/templates/{id}          → Delete a profile

All write endpoints require coordinator authentication.
"""

import io
import os
import tempfile
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TemplateProfile, User
from ..auth import get_current_active_coordinator, get_current_user
from ..utils.template_parser import StructuralTemplateParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["template-profiles"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ContainerSchema(BaseModel):
    day: str
    start_hour: int
    end_hour: int
    duration: int
    session_type: str      # "lecture" | "practical" | "tutorial"
    group_label: str
    col_index: int
    row_index: int


class PreviewResponse(BaseModel):
    file_type: str
    shape: dict
    containers: List[ContainerSchema]
    container_count: int
    session_type_counts: dict


class SaveProfileRequest(BaseModel):
    name: str
    school_name: Optional[str] = None
    original_filename: Optional[str] = None
    file_type: str
    shape: dict
    containers: List[ContainerSchema]


class TemplateProfileResponse(BaseModel):
    id: int
    name: str
    school_name: Optional[str]
    is_active: bool
    original_filename: Optional[str]
    file_type: str
    container_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateProfileDetailResponse(TemplateProfileResponse):
    shape: Optional[dict]
    containers: List[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv", "docx"}

def _resolve_file_type(filename: str, content_type: str) -> str:
    """Resolve the logical file type from the filename extension or MIME type."""
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "doc":
            raise HTTPException(
                status_code=400,
                detail="Legacy .doc format is not supported. Please open the file in Word and 'Save As' a modern .docx file."
            )
        if ext in ALLOWED_EXTENSIONS:
            return ext
            
    if content_type == "application/msword":
         raise HTTPException(
             status_code=400,
             detail="Legacy .doc format is not supported. Please open the file in Word and 'Save As' a modern .docx file."
         )
         
    if content_type in ALLOWED_MIME_TYPES:
        return ALLOWED_MIME_TYPES[content_type]
        
    raise HTTPException(
        status_code=400,
        detail="Unsupported file type. Please upload a Word (.docx) or Excel (.xlsx/.csv) file.",
    )


@router.post("/upload-preview", response_model=PreviewResponse)
async def upload_preview(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_coordinator),
):
    """
    Parse an uploaded template file and return the extracted containers
    for UI preview (without saving anything to the database).

    The frontend can display these containers and allow the coordinator to
    confirm, adjust labels, or re-upload before saving.
    """
    file_type = _resolve_file_type(file.filename or "", file.content_type or "")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 10 * 1024 * 1024:  # 10 MB cap
        raise HTTPException(status_code=400, detail="File is too large (max 10 MB).")

    # Write to a temp file so the parser can open it normally
    suffix = f".{file_type}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parser = StructuralTemplateParser(tmp_path, file_type)
        result = parser.parse()
    except Exception as e:
        logger.exception("Failed to parse template '%s': %s", file.filename, e)
        raise HTTPException(
            status_code=422,
            detail="Could not parse the uploaded template. Please ensure it is a valid Word (.docx) or Excel (.xlsx/.csv) file.",
        )

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    containers = result.get("containers", [])
    shape = result.get("shape", {})

    if not containers:
        raise HTTPException(
            status_code=422,
            detail=(
                "No schedulable containers found in the file. "
                "Make sure cells contain the words 'Lecture', 'Lab', 'Tutorial', or 'Practical'."
            ),
        )

    # Count by session type
    type_counts: dict = {}
    for c in containers:
        st = c.get("session_type", "unknown")
        type_counts[st] = type_counts.get(st, 0) + 1

    return PreviewResponse(
        file_type=file_type,
        shape=shape,
        containers=[ContainerSchema(**c) for c in containers],
        container_count=len(containers),
        session_type_counts=type_counts,
    )


@router.post("/save", response_model=TemplateProfileDetailResponse, status_code=201)
def save_profile(
    body: SaveProfileRequest,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """
    Save a confirmed template layout as a named TemplateProfile in the database.
    The coordinator calls this after reviewing the preview.
    """
    if not body.containers:
        raise HTTPException(status_code=400, detail="Cannot save a profile with no containers.")

    profile = TemplateProfile(
        name=body.name,
        school_name=body.school_name,
        original_filename=body.original_filename,
        file_type=body.file_type,
        shape=body.shape,
        containers=[c.model_dump() for c in body.containers],
        is_active=False,
        created_at=datetime.now(timezone.utc).isoformat(),
        created_by_id=current_user.id,
        university_id=current_user.university_id,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    logger.info(
        "TemplateProfile '%s' created by %s (%d containers)",
        profile.name, current_user.email, len(profile.containers),
    )

    return _profile_detail_response(profile)


@router.get("/", response_model=List[TemplateProfileResponse])
def list_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all saved template profiles."""
    profiles = db.query(TemplateProfile).order_by(TemplateProfile.id.desc()).all()
    return [
        TemplateProfileResponse(
            id=p.id,
            name=p.name,
            school_name=p.school_name,
            is_active=p.is_active,
            original_filename=p.original_filename,
            file_type=p.file_type,
            container_count=len(p.containers or []),
            created_at=p.created_at,
        )
        for p in profiles
    ]


@router.get("/{profile_id}", response_model=TemplateProfileDetailResponse)
def get_profile(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full details of a single template profile including all containers."""
    profile = db.query(TemplateProfile).filter(TemplateProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Template profile not found.")
    return _profile_detail_response(profile)


@router.put("/{profile_id}/activate", response_model=TemplateProfileResponse)
def activate_profile(
    profile_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """
    Set one profile as the active template for generation and export.
    Deactivates all other profiles.
    """
    profile = db.query(TemplateProfile).filter(TemplateProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Template profile not found.")

    # Deactivate others
    db.query(TemplateProfile).filter(TemplateProfile.id != profile_id).update(
        {"is_active": False}, synchronize_session=False
    )
    profile.is_active = True
    db.commit()
    db.refresh(profile)

    logger.info("TemplateProfile %d ('%s') set as active", profile.id, profile.name)

    return TemplateProfileResponse(
        id=profile.id,
        name=profile.name,
        school_name=profile.school_name,
        is_active=profile.is_active,
        original_filename=profile.original_filename,
        file_type=profile.file_type,
        container_count=len(profile.containers or []),
        created_at=profile.created_at,
    )


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: int,
    current_user: User = Depends(get_current_active_coordinator),
    db: Session = Depends(get_db),
):
    """Delete a template profile."""
    profile = db.query(TemplateProfile).filter(TemplateProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Template profile not found.")
    db.delete(profile)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _profile_detail_response(profile: TemplateProfile) -> TemplateProfileDetailResponse:
    return TemplateProfileDetailResponse(
        id=profile.id,
        name=profile.name,
        school_name=profile.school_name,
        is_active=profile.is_active,
        original_filename=profile.original_filename,
        file_type=profile.file_type,
        container_count=len(profile.containers or []),
        created_at=profile.created_at,
        shape=profile.shape,
        containers=profile.containers or [],
    )
