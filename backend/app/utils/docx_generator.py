from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from typing import Dict, Any

class DocxGenerator:
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.document = Document()
        self._setup_styles()

    def _setup_styles(self):
        style = self.document.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(8)

    def generate(self, data: Dict[str, Any]):
        self._add_header(data)
        
        days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
        grid = data.get("grid_data", {})
        
        for day in days:
            self._add_day_section(day, grid.get(day, {}))
            self.document.add_page_break()
            
        self._add_footer_keys()
        self.document.save(self.output_path)

    def _add_header(self, data):
        p = self.document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("THE UNIVERSITY OF ZAMBIA\n")
        run.bold = True
        run.font.size = Pt(14)
        
        run = p.add_run("SCHOOL OF ENGINEERING\n")
        run.bold = True
        run.font.size = Pt(12)
        
        half_text = "FIRST HALF" if data.get('academic_half') == "first_half" else "SECOND HALF"
        if data.get('semester', '').lower() == "term 2": # Fallback logic if needed
             half_text = "SECOND HALF"
             
        run = p.add_run(f"{half_text} {data['year']} ACADEMIC YEAR UG TIME-TABLE\n")
        run.bold = True
        
        self.document.add_paragraph("---")

    def _add_day_section(self, day: str, day_data: Dict[str, Any]):
        h = self.document.add_heading(day, level=2)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Table Structure:
        # Time | 2nd Year (2 cols) | 3rd Year (5 cols) | 4th Year (5 cols) | 5th Year (5 cols)
        # Total columns: 1 + 2 + 5 + 5 + 5 = 18 columns
        
        table = self.document.add_table(rows=2, cols=18)
        table.style = 'Table Grid'
        table.autofit = False
        
        # Header Row 1: Years
        # Merging logic is complex, simplified for MVP:
        row0 = table.rows[0].cells
        row0[0].text = "HOURS"
        row0[1].text = "2ND YEAR"
        row0[3].text = "3RD YEAR"
        row0[8].text = "4TH YEAR"
        row0[13].text = "5TH YEAR"
        
        # Merge cells for years (simplified range)
        row0[1].merge(row0[2]) # 2nd year covers 2 cols
        row0[3].merge(row0[7]) # 3rd year covers 5 cols
        row0[8].merge(row0[12]) # 4th year
        row0[13].merge(row0[17]) # 5th year
        
        # Header Row 2: Sub-headers
        row1 = table.rows[1].cells
        headers = ["", "GEN LG1", "GEN LG2"] 
        depts = ["AEN", "CEE", "EEE", "GEE", "MEC"]
        headers.extend(depts * 3) # Repeat for 3rd, 4th, 5th
        
        for i, text in enumerate(headers):
            if i < len(row1):
                row1[i].text = text
                
        # Data Rows
        hours = [f"{h:02d}:00" for h in range(7, 19)]
        col_map = self._get_column_mapping()
        
        for hour in hours:
            row_cells = table.add_row().cells
            row_cells[0].text = f"{hour} -- {int(hour[:2])+1:02d}.00"
            
            # Fill data
            hour_data = day_data.get(hour, {})
            for key, entries in hour_data.items():
                if key in col_map:
                    col_idx = col_map[key]
                    text = "\n".join([f"{e['course_code']} {e['room_name']}" for e in entries])
                    row_cells[col_idx].text = text

    def _get_column_mapping(self):
        """Map generic keys to column indices"""
        mapping = {
            "GEN LG1": 1, "GEN LG2": 2,
            "3-AEN": 3, "3-CEE": 4, "3-EEE": 5, "3-GEE": 6, "3-MEC": 7,
            "4-AEN": 8, "4-CEE": 9, "4-EEE": 10, "4-GEE": 11, "4-MEC": 12,
            "5-AEN": 13, "5-CEE": 14, "5-EEE": 15, "5-GEE": 16, "5-MEC": 17,
        }
        return mapping

    def _add_footer_keys(self):
        self.document.add_paragraph("\n")
        p = self.document.add_paragraph()
        run = p.add_run("ROOM CODES KEY:\n")
        run.bold = True
        p.add_run("- MLT: School of Mines Lecture Theatre\n")
        p.add_run("- LT: Lecture Theatre, School of Engineering\n")
        # Add more keys as needed...
