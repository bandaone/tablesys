"""Centralized access policy helpers.

This module provides a single place for role and account-state authorization
checks so routers and auth dependencies can share consistent behavior.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException, status

from .models import UserRole


def _normalize_role(role: UserRole | str | None) -> str:
    if role is None:
        return ""
    if hasattr(role, "value"):
        return str(role.value).lower()
    return str(role).lower()


def user_has_any_role(role: UserRole | str | None, allowed_roles: Iterable[UserRole | str]) -> bool:
    normalized_role = _normalize_role(role)
    normalized_allowed = {_normalize_role(r) for r in allowed_roles}
    return normalized_role in normalized_allowed


def enforce_user_roles(
    role: UserRole | str | None,
    allowed_roles: Iterable[UserRole | str],
    detail: str,
) -> None:
    if not user_has_any_role(role, allowed_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def enforce_active_account(is_active: bool, detail: str = "Inactive user") -> None:
    if not is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def enforce_active_student(is_active: bool, detail: str = "Student account is inactive") -> None:
    if not is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
