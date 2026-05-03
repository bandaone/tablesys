"""
Branding Router — authenticated.
Returns the current user's university branding for the frontend app shell.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models import University, User
from ..auth import get_current_user

router = APIRouter(prefix="/api/v1/universities", tags=["branding"])


class BrandingResponse(BaseModel):
    university_id: int
    name: str
    short_name: Optional[str]
    domain: str
    logo_url: Optional[str]
    primary_color: str
    secondary_color: str
    tagline: Optional[str]
    plan_tier: str
    max_users: int

    class Config:
        from_attributes = True


@router.get("/me/branding", response_model=BrandingResponse)
def get_my_university_branding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the authenticated user's university branding.
    Called immediately after login to skin the app shell.
    """
    if current_user.university_id is None:
        # SUPERADMIN has no university — return platform defaults
        return BrandingResponse(
            university_id=0,
            name="TableSys Platform",
            short_name="TABLESYS",
            domain="platform",
            logo_url=None,
            primary_color="#0f172a",
            secondary_color="#7c3aed",
            tagline="Multi-University Timetable Platform",
            plan_tier="platform",
            max_users=0,
        )

    uni = db.query(University).filter(University.id == current_user.university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University record not found.")

    return BrandingResponse(
        university_id=uni.id,
        name=uni.name,
        short_name=uni.short_name,
        domain=uni.domain,
        logo_url=uni.logo_url,
        primary_color=uni.primary_color,
        secondary_color=uni.secondary_color,
        tagline=uni.tagline,
        plan_tier=uni.plan_tier,
        max_users=uni.max_users,
    )
