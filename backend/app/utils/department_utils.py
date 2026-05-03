"""
Helpers for identifying the general-engineering department consistently.

Some deployments use code `GEN`, while others historically used `ENG`.
The scheduling logic should treat both as the same semantic department.
"""

from typing import Optional

from sqlalchemy.orm import Session

from ..models import Department


GENERAL_DEPARTMENT_CODES = {"GEN", "ENG"}


def is_general_department(department: Optional[Department]) -> bool:
    """Return True when a department row represents General Engineering."""
    if department is None:
        return False

    code = (department.code or "").strip().upper()
    name = (department.name or "").strip().lower()

    return (
        code in GENERAL_DEPARTMENT_CODES
        or name == "general"
        or "general engineering" in name
    )


def find_general_department(db: Session) -> Optional[Department]:
    """Resolve the General Engineering department regardless of local code choice."""
    departments = db.query(Department).all()
    for department in departments:
        if is_general_department(department):
            return department
    return None
