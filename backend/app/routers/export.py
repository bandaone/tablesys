"""
Export Router

Provides endpoints for exporting timetable data in DOCX, Excel, and JSON formats.
All endpoints require JWT authentication.

Endpoints:
    GET /export/timetable/{id}/docx   - Export specific timetable as DOCX
    GET /export/timetable/{id}/excel  - Export specific timetable as XLSX
    GET /export/active/docx           - Export active timetable as DOCX
    GET /export/active/excel          - Export active timetable as XLSX
    GET /export/active/json           - Export active timetable as JSON grid
"""

from __future__ import annotations

import os
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..services.export_service import ExportService
from ..utils.docx_generator import DocxGenerator
from ..utils.pdf_generator import PDFGenerator

router = APIRouter(
    prefix="/export",
    tags=["export"],
    responses={404: {"description": "Not found"}},
)

EXPORTS_DIR = "exports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_exports_dir() -> None:
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def _docx_path(label: str) -> str:
    return os.path.join(EXPORTS_DIR, f"timetable_{label}.docx")


def _excel_path(label: str) -> str:
    return os.path.join(EXPORTS_DIR, f"timetable_{label}.xlsx")


def _pdf_path(label: str) -> str:
    return os.path.join(EXPORTS_DIR, f"timetable_{label}.pdf")


# ---------------------------------------------------------------------------
# Specific timetable by ID
# ---------------------------------------------------------------------------

@router.get("/timetable/{timetable_id}/docx", summary="Export timetable as DOCX")
def export_timetable_docx(
    timetable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Generate and download the traditional-format Word document for a timetable.
    """
    _ensure_exports_dir()
    export_service = ExportService(db)

    try:
        data = export_service.get_traditional_export_data(timetable_id, university_id=current_user.university_id)
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Timetable not found.")

    filename = f"timetable_{timetable_id}_{data['semester']}_{data['year']}.docx"
    filepath = _docx_path(f"{timetable_id}_{data['semester']}_{data['year']}")

    generator = DocxGenerator(filepath)
    generator.generate(data)

    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/timetable/{timetable_id}/pdf", summary="Export timetable as PDF")
def export_timetable_pdf(
    timetable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Generate and download a professional PDF document for a timetable.

    The PDF contains one page per working day (Monday-Friday) with the
    traditional grid layout, tenant branding, and a room-key page.
    """
    _ensure_exports_dir()
    export_service = ExportService(db)

    try:
        data = export_service.get_traditional_export_data(timetable_id, university_id=current_user.university_id)
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Timetable not found.")

    filename = f"timetable_{timetable_id}_{data['semester']}_{data['year']}.pdf"
    filepath = _pdf_path(f"{timetable_id}_{data['semester']}_{data['year']}")

    generator = PDFGenerator(filepath)
    generator.generate(data)

    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/pdf",
    )


# ---------------------------------------------------------------------------
# Active timetable convenience endpoints
# ---------------------------------------------------------------------------

@router.get("/active/docx", summary="Export active timetable as DOCX")
def export_active_docx(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Generate and download the active timetable as a Word document.
    Returns 404 if no timetable is currently active.
    """
    _ensure_exports_dir()
    export_service = ExportService(db)

    try:
        data = export_service.get_active_timetable_export_data(university_id=current_user.university_id)
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Timetable not found.")

    filename = f"active_timetable_{data['semester']}_{data['year']}.docx"
    filepath = _docx_path(f"active_{data['semester']}_{data['year']}")

    generator = DocxGenerator(filepath)
    generator.generate(data)

    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/active/pdf", summary="Export active timetable as PDF")
def export_active_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Generate and download the active timetable as a professional PDF document.
    Returns 404 if no timetable is currently active.
    """
    _ensure_exports_dir()
    export_service = ExportService(db)

    try:
        data = export_service.get_active_timetable_export_data(university_id=current_user.university_id)
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Timetable not found.")

    filename = f"active_timetable_{data['semester']}_{data['year']}.pdf"
    filepath = _pdf_path(f"active_{data['semester']}_{data['year']}")

    generator = PDFGenerator(filepath)
    generator.generate(data)

    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/pdf",
    )


@router.get("/active/json", summary="Export active timetable as JSON")
def export_active_json(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    Return the active timetable grid as a JSON object.

    The grid structure mirrors the DOCX/XLSX layout:
        { DAY: { HH:MM: { column_key: [slot_entries] } } }

    Returns 404 if no timetable is currently active.
    """
    export_service = ExportService(db)

    try:
        data = export_service.get_active_timetable_export_data(university_id=current_user.university_id)
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Timetable not found.")

    # Convert defaultdict tree to plain dicts for JSON serialisation
    grid = data["grid_data"]
    plain_grid = {
        day: {hour: dict(cols) for hour, cols in hours.items()}
        for day, hours in grid.items()
    }

    return JSONResponse(
        content={
            "timetable_name": data["timetable_name"],
            "semester": data["semester"],
            "year": data["year"],
            "academic_half": data["academic_half"],
            "grid": plain_grid,
        }
    )
