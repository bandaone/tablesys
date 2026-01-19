from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from ..services.export_service import ExportService
from ..utils.docx_generator import DocxGenerator
import os

router = APIRouter(
    prefix="/export",
    tags=["export"],
    responses={404: {"description": "Not found"}},
)

@router.get("/timetable/{timetable_id}/docx")
def export_timetable_docx(timetable_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Generate and retrieve the traditional format DOCX for a timetable.
    """
    export_service = ExportService(db)
    data = export_service.get_traditional_export_data(timetable_id)
    
    # Generate file
    filename = f"timetable_{timetable_id}_{data['semester']}_{data['year']}.docx"
    filepath = os.path.join("exports", filename)
    os.makedirs("exports", exist_ok=True)
    
    generator = DocxGenerator(filepath)
    generator.generate(data)
    
    from fastapi.responses import FileResponse
    return FileResponse(filepath, filename=filename, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
