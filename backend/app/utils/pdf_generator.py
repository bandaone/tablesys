"""
PDF Timetable Generator

Generates a professional PDF timetable in landscape orientation with tenant branding.
Uses a grid layout similar to the Excel export with proper formatting and colors.

The PDF includes:
  - University header with dynamic tenant branding
  - Timetable grid (07:00 - 18:00)
  - Color-coded year groups and departments
  - One page per day (Monday-Friday)
  - Room key legend at the end
"""

from __future__ import annotations

from typing import Any, Dict, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
)
from reportlab.pdfgen import canvas


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAYS: List[str] = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
HOURS: List[str] = [f"{h:02d}:00" for h in range(7, 19)]  # 07:00 – 18:00

# Column layout matching Excel generator
COLUMNS: List[tuple[str, str]] = [
    ("HOURS", ""),
    ("GEN LG1", "2ND YEAR"),
    ("GEN LG2", "2ND YEAR"),
    ("AEN", "3RD YEAR"),
    ("CEE", "3RD YEAR"),
    ("EEE", "3RD YEAR"),
    ("GEE", "3RD YEAR"),
    ("MEC", "3RD YEAR"),
    ("AEN", "4TH YEAR"),
    ("CEE", "4TH YEAR"),
    ("EEE", "4TH YEAR"),
    ("GEE", "4TH YEAR"),
    ("MEC", "4TH YEAR"),
    ("AEN", "5TH YEAR"),
    ("CEE", "5TH YEAR"),
    ("EEE", "5TH YEAR"),
    ("GEE", "5TH YEAR"),
    ("MEC", "5TH YEAR"),
]

# Map export_service column keys to column indices
COL_KEY_TO_IDX: Dict[str, int] = {
    "GEN LG1": 1, "GEN LG2": 2,
    "3-AEN": 3, "3-CEE": 4, "3-EEE": 5, "3-GEE": 6, "3-MEC": 7,
    "4-AEN": 8, "4-CEE": 9, "4-EEE": 10, "4-GEE": 11, "4-MEC": 12,
    "5-AEN": 13, "5-CEE": 14, "5-EEE": 15, "5-GEE": 16, "5-MEC": 17,
}

# Branding Colors (RGB)
COLOR_DARK_BLUE = colors.HexColor("#003366")
COLOR_ORANGE = colors.HexColor("#FF8C00")
COLOR_LIGHT_BLUE = colors.HexColor("#E8EFF7")
COLOR_WHITE = colors.white
COLOR_GRAY = colors.HexColor("#F5F5F5")

ROOM_KEY_NOTES = [
    "MLT  - School of Mines Lecture Theatre",
    "LT   - Lecture Theatre, School of Engineering",
    "DR   - Drawing Room",
    "CR   - Computer Lab",
    "CELAB- Civil Engineering Laboratory",
    "EELAB- Electrical Engineering Laboratory",
]


# ---------------------------------------------------------------------------
# PDF Generator
# ---------------------------------------------------------------------------

class PDFGenerator:
    """
    Generates a professional PDF timetable from the grid data produced by
    ExportService.get_traditional_export_data().

    Usage::
        generator = PDFGenerator(output_path)
        generator.generate(export_data)
    """

    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self.story = []
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Create custom paragraph styles for the PDF."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name="TenantTitle",
                parent=self.styles["Heading1"],
                fontSize=14,
                textColor=COLOR_DARK_BLUE,
                alignment=1,  # Center
                spaceAfter=12,
                fontName="Helvetica-Bold",
            )
        )

        # Day header style
        self.styles.add(
            ParagraphStyle(
                name="DayHeader",
                parent=self.styles["Heading2"],
                fontSize=12,
                textColor=COLOR_WHITE,
                backColor=COLOR_DARK_BLUE,
                alignment=1,
                spaceAfter=6,
                fontName="Helvetica-Bold",
            )
        )

    def generate(self, data: Dict[str, Any]) -> str:
        """
        Build the PDF document and save it.

        Args:
            data: Dict returned by ExportService.get_traditional_export_data()

        Returns:
            Absolute path to the saved PDF file.
        """
        # Setup document
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=landscape(A3),
            rightMargin=10 * mm,
            leftMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
        )

        grid_data = data.get("grid_data", {})

        # Add timetable for each day
        for idx, day in enumerate(DAYS):
            if idx > 0:
                self.story.append(PageBreak())
            self._add_day_timetable(day, grid_data.get(day, {}), data)

        # Add room key page
        self.story.append(PageBreak())
        self._add_room_key(data)

        # Build PDF
        doc.build(self.story, onFirstPage=self._add_footer, onLaterPages=self._add_footer)
        return self.output_path

    def _add_page_masthead(self, meta: Dict[str, Any]) -> None:
        """Add a compact branded header above each page grid."""
        half = "First Half" if meta.get("academic_half", "first_half") == "first_half" else "Second Half"
        year = meta.get("year", "")
        university_name = meta.get("university_name", "UNIVERSITY")
        timetable_name = meta.get("timetable_name", "Timetable")
        semester = meta.get("semester", "")

        title_text = (
            f"<para align=center>"
            f"<font size=16><b>{university_name.upper()}</b></font><br/>"
            f"<font size=12><b>{timetable_name}</b></font><br/>"
            f"<font size=10>{semester} • {half} • {year} Academic Year</font>"
            f"</para>"
        )
        self.story.append(Paragraph(title_text, self.styles["TenantTitle"]))
        self.story.append(Spacer(1, 3 * mm))

    def _add_day_timetable(self, day: str, day_data: Dict[str, Any], meta: Dict[str, Any]) -> None:
        """Add timetable grid for a specific day."""
        self._add_page_masthead(meta)

        # Day header
        day_header = Paragraph(
            f"<para align=center><b>{day}</b></para>",
            self.styles["DayHeader"]
        )
        self.story.append(day_header)
        self.story.append(Spacer(1, 2 * mm))

        # Build table data
        table_data = self._build_table_data(day_data)

        # Create table
        available_width = landscape(A3)[0] - (20 * mm)
        time_col_width = 18 * mm
        other_col_width = (available_width - time_col_width) / (len(COLUMNS) - 1)
        col_widths = [time_col_width] + [other_col_width] * (len(COLUMNS) - 1)
        
        table = Table(table_data, colWidths=col_widths, repeatRows=2)

        # Table styling
        table_style = self._create_table_style(len(table_data))
        table.setStyle(table_style)

        self.story.append(table)

    def _build_table_data(self, day_data: Dict[str, Any]) -> List[List[str]]:
        """Build the table data matrix for a day."""
        # Year group header row
        year_header = [""]  # Empty for HOURS column
        year_header += ["2ND YEAR", "2ND YEAR"]
        year_header += ["3RD YEAR"] * 5
        year_header += ["4TH YEAR"] * 5
        year_header += ["5TH YEAR"] * 5

        # Department header row
        dept_header = ["HOURS"]
        for col, _ in COLUMNS[1:]:  # Skip HOURS
            dept_header.append(col)

        # Data rows (one per hour)
        data_rows = []
        for hour in HOURS:
            row = [hour]  # Time column
            hour_data = day_data.get(hour, {})

            # Fill each column
            for col_name, _ in COLUMNS[1:]:
                # Map column name to key
                col_key = None
                if "GEN" in col_name:
                    col_key = col_name
                else:
                    # Find matching key like "3-AEN", "4-CEE", etc.
                    for key in COL_KEY_TO_IDX:
                        if col_name in key and key in hour_data:
                            col_key = key
                            break

                # Get slot data
                if col_key and col_key in hour_data:
                    slots = hour_data[col_key]
                    if slots:
                        # Format slot info
                        slot = slots[0]  # Take first slot if multiple
                        cell_text = (
                            f"{slot.get('course_code', '')}\n"
                            f"{slot.get('room_name', '')}\n"
                            f"{slot.get('lecturer_name', '')}"
                        )
                        row.append(cell_text)
                    else:
                        row.append("")
                else:
                    row.append("")

            data_rows.append(row)

        # Combine all rows
        return [year_header, dept_header] + data_rows

    def _create_table_style(self, num_rows: int) -> TableStyle:
        """Create the table style with tenant colors."""
        style_commands = [
            # General
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.2),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEADING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),

            # Year header row (row 0)
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_DARK_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7.2),

            # Department header row (row 1)
            ("BACKGROUND", (0, 1), (-1, 1), COLOR_ORANGE),
            ("TEXTCOLOR", (0, 1), (-1, 1), COLOR_WHITE),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, 1), 7.2),

            # Time column (first column)
            ("BACKGROUND", (0, 2), (0, -1), COLOR_LIGHT_BLUE),
            ("FONTNAME", (0, 2), (0, -1), "Helvetica-Bold"),

            # Alternate row colors for data
            ("ROWBACKGROUNDS", (1, 2), (-1, -1), [COLOR_WHITE, COLOR_GRAY]),
        ]

        return TableStyle(style_commands)

    def _add_room_key(self, meta: Dict[str, Any]) -> None:
        """Add room key legend page."""
        self._add_page_masthead(meta)
        title = Paragraph("<para align=center><b>ROOM KEY</b></para>", self.styles["Heading2"])
        self.story.append(title)
        self.story.append(Spacer(1, 5 * mm))

        for note in ROOM_KEY_NOTES:
            para = Paragraph(f"• {note}", self.styles["Normal"])
            self.story.append(para)
            self.story.append(Spacer(1, 2 * mm))

    def _add_footer(self, canvas_obj: canvas.Canvas, doc: Any) -> None:
        """Add footer to each page."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.grey)
        
        # Page number
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.drawRightString(landscape(A3)[0] - 15 * mm, 5 * mm, text)
        
        # Generic footer — tenant name injected via title page
        canvas_obj.drawString(15 * mm, 5 * mm, "Generated by TABLESYS Timetable Management System")
        
        canvas_obj.restoreState()
