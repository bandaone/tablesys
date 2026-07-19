from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_active_tenant_admin, get_current_user
from ..database import get_db
from ..models import AcademicCalendar, ActivityType as ActivityTypeModel, University, User
from ..schemas import InstitutionSetupPayload, InstitutionSetupResponse, UniversitySchedulingPolicy
from ..services.institution_templates import build_policy, get_template_payload, template_catalog
from ..utils.audit_logger import AuditLogger


router = APIRouter(prefix="/api/v1/institution-setup", tags=["institution-setup"])


def _tenant_id(current_user: User) -> int:
    if current_user.university_id is None:
        raise HTTPException(status_code=403, detail="Tenant-scoped access required")
    return current_user.university_id


def _serialize_calendar(calendar: AcademicCalendar | None) -> Dict[str, Any] | None:
    if calendar is None:
        return None
    return {
        "id": calendar.id,
        "name": calendar.name,
        "days_of_week": calendar.days_of_week,
        "start_time": calendar.start_time.strftime("%H:%M"),
        "end_time": calendar.end_time.strftime("%H:%M"),
        "slot_duration_minutes": calendar.slot_duration_minutes,
        "is_default": calendar.is_default,
    }


@router.get("/templates")
async def list_setup_templates(
    current_user: User = Depends(get_current_user),
):
    _tenant_id(current_user)
    return {"templates": template_catalog()}


@router.get("/", response_model=InstitutionSetupResponse)
async def get_institution_setup(
    current_user: User = Depends(get_current_active_tenant_admin),
    db: Session = Depends(get_db),
):
    tenant_id = _tenant_id(current_user)
    university = db.query(University).filter(University.id == tenant_id).first()
    calendar = (
        db.query(AcademicCalendar)
        .filter(AcademicCalendar.university_id == tenant_id, AcademicCalendar.is_default == True)
        .first()
    )
    activity_types = (
        db.query(ActivityTypeModel)
        .filter(ActivityTypeModel.university_id == tenant_id)
        .order_by(ActivityTypeModel.display_name.asc())
        .all()
    )
    raw_policy = dict(university.scheduling_policy or build_policy("custom"))
    active_days = list(calendar.days_of_week or []) if calendar else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    return {
        "university_id": university.id,
        "template_key": raw_policy.get("institution_template_key", "custom"),
        "scheduling_policy": UniversitySchedulingPolicy(**raw_policy),
        "room_tags": list(raw_policy.get("room_tag_catalog") or []),
        "activity_types": activity_types,
        "calendar": _serialize_calendar(calendar),
        "onboarding_completed_at": getattr(university, "onboarding_completed_at", None),
        "active_days": active_days,
    }


@router.put("/", response_model=InstitutionSetupResponse)
async def save_institution_setup(
    request: Request,
    payload: InstitutionSetupPayload,
    current_user: User = Depends(get_current_active_tenant_admin),
    db: Session = Depends(get_db),
):
    tenant_id = _tenant_id(current_user)
    university = db.query(University).filter(University.id == tenant_id).first()
    if not university:
        raise HTTPException(status_code=404, detail="University not found")

    template = get_template_payload(payload.template_key)
    policy_dict = build_policy(payload.template_key, payload.scheduling_policy.model_dump())
    policy_dict["room_tag_catalog"] = list(payload.room_tags or template.get("room_tags") or [])
    policy_dict["lunch_start"] = payload.lunch_start
    policy_dict["lunch_end"] = payload.lunch_end
    university.scheduling_policy = policy_dict
    if hasattr(type(university), "onboarding_completed_at"):
        university.onboarding_completed_at = datetime.now(timezone.utc)

    calendar = (
        db.query(AcademicCalendar)
        .filter(AcademicCalendar.university_id == tenant_id, AcademicCalendar.is_default == True)
        .first()
    )
    if calendar is None:
        calendar = AcademicCalendar(university_id=tenant_id, is_default=True)
        db.add(calendar)

    calendar.name = payload.calendar_name
    calendar.days_of_week = payload.days_of_week
    calendar.start_time = datetime.strptime(payload.start_time, "%H:%M").time()
    calendar.end_time = datetime.strptime(payload.end_time, "%H:%M").time()
    calendar.slot_duration_minutes = payload.slot_duration_minutes

    activity_rows = payload.activity_types or template.get("activity_types") or []
    existing = {
        row.key: row
        for row in db.query(ActivityTypeModel).filter(ActivityTypeModel.university_id == tenant_id).all()
    }
    seen_keys = set()
    for item in activity_rows:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        key = str(data["key"]).strip().lower()
        seen_keys.add(key)
        row = existing.get(key)
        if row is None:
            row = ActivityTypeModel(university_id=tenant_id, key=key)
            db.add(row)
        row.display_name = data["display_name"]
        row.color = data.get("color", "#3B82F6")
        row.default_duration_periods = data.get("default_duration_periods", 1)
        row.default_frequency_per_week = data.get("default_frequency_per_week", 1)
        row.requires_subgroups = data.get("requires_subgroups", False)
        row.resource_tags_required = data.get("resource_tags_required")
        row.counts_toward_contact_hours = data.get("counts_toward_contact_hours", True)
        row.is_active = data.get("is_active", True)

    for key, row in existing.items():
        if key not in seen_keys:
            row.is_active = False

    db.commit()
    db.refresh(university)
    if calendar.id:
        db.refresh(calendar)

    activity_types = (
        db.query(ActivityTypeModel)
        .filter(ActivityTypeModel.university_id == tenant_id)
        .order_by(ActivityTypeModel.display_name.asc())
        .all()
    )
    AuditLogger.log_event(
        event_type="UPDATE_INSTITUTION_SETUP",
        request=request,
        user_id=current_user.id,
        username=current_user.username,
        details={
            "tenant_id": tenant_id,
            "template_key": policy_dict.get("institution_template_key", payload.template_key),
            "room_tag_count": len(policy_dict.get("room_tag_catalog") or []),
            "activity_type_count": len(activity_rows),
        },
    )
    return {
        "university_id": university.id,
        "template_key": policy_dict.get("institution_template_key", payload.template_key),
        "scheduling_policy": UniversitySchedulingPolicy(**policy_dict),
        "room_tags": list(policy_dict.get("room_tag_catalog") or []),
        "activity_types": activity_types,
        "calendar": _serialize_calendar(calendar),
        "onboarding_completed_at": getattr(university, "onboarding_completed_at", None),
        "active_days": list(calendar.days_of_week or []),
    }
