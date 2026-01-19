
import sys
import os


sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models import Timetable
from app.services.export_service import ExportService
from app.utils.docx_generator import DocxGenerator

def test_export():
    print("[*] Starting Export Test...")
    
    db = SessionLocal()
    try:
        # Get the timetable created in previous test
        tt = db.query(Timetable).first()
        if not tt:
            print("[-] No timetable found. Run test_generation.py first.")
            return

        print(f"[*] Found Timetable: {tt.name} ({tt.academic_half})")
        
        # Prepare Data
        service = ExportService(db)
        data = service.get_traditional_export_data(tt.id)
        
        print(f"[*] Data Prepared. Grid keys: {list(data.get('grid_data', {}).keys())}")
        
        # Generate DOCX
        output_file = "test_timetable_export.docx"
        generator = DocxGenerator(output_path=output_file)
        generator.generate(data)
        
        print(f"[+] DOCX Generated: {os.path.abspath(output_file)}")
        
    except Exception as e:
        print(f"[-] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_export()
