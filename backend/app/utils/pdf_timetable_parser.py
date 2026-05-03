"""
PDF Timetable Parser

Parses university timetable PDFs into structured data
compatible with the TABLESYS database schema.

Handles:
- Multi-page timetable PDFs (one day per page or multi-day per page)
- Course code extraction with group notation cleanup
- Room code identification and metadata mapping
- Deduplication of courses appearing across multiple days
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

try:
    import pdfplumber
except ImportError as e:
    raise ImportError(
        "pdfplumber is required for PDF parsing. "
        "Install it with: pip install pdfplumber==0.10.3"
    ) from e

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

PROGRAMS = ["AEN", "CEE", "EEE", "GEE", "MEC"]

# Known room codes and their metadata.
# Extend this dict as new rooms are identified from the PDF KEY section.
ROOM_METADATA: Dict[str, Dict] = {
    "MLT": {
        "name": "School of Mines Lecture Theatre",
        "capacity": 200,
        "room_type": "lecture_hall",
    },
    "LT": {
        "name": "Lecture Theatre, School of Engineering",
        "capacity": 150,
        "room_type": "lecture_hall",
    },
    "ENLT1": {
        "name": "Engineering New Lecture Theatre 1",
        "capacity": 80,
        "room_type": "lecture_hall",
    },
    "ENLT2": {
        "name": "Engineering New Lecture Theatre 2",
        "capacity": 80,
        "room_type": "lecture_hall",
    },
    "NLR1": {
        "name": "New Lecture Room 1",
        "capacity": 60,
        "room_type": "lecture_hall",
    },
    "NLR2": {
        "name": "New Lecture Room 2",
        "capacity": 60,
        "room_type": "lecture_hall",
    },
    "NLR3": {
        "name": "New Lecture Room 3",
        "capacity": 60,
        "room_type": "lecture_hall",
    },
    "NLR4": {
        "name": "New Lecture Room 4",
        "capacity": 60,
        "room_type": "lecture_hall",
    },
    "DR1": {
        "name": "Drawing Room 1",
        "capacity": 60,
        "room_type": "drawing_room",
    },
    "DR2": {
        "name": "Drawing Room 2",
        "capacity": 60,
        "room_type": "drawing_room",
    },
    "COMPLAB": {
        "name": "Computer Laboratory",
        "capacity": 40,
        "room_type": "lab",
    },
    "SURV": {
        "name": "Surveying Room",
        "capacity": 30,
        "room_type": "surveying_room",
    },
    "SEM1": {
        "name": "Seminar Room 1",
        "capacity": 30,
        "room_type": "seminar_room",
    },
    "SEM2": {
        "name": "Seminar Room 2",
        "capacity": 30,
        "room_type": "seminar_room",
    },
    "LAB1": {
        "name": "Engineering Laboratory 1",
        "capacity": 40,
        "room_type": "lab",
    },
    "LAB2": {
        "name": "Engineering Laboratory 2",
        "capacity": 40,
        "room_type": "lab",
    },
    "ELAB": {
        "name": "Electrical Engineering Laboratory",
        "capacity": 30,
        "room_type": "lab",
    },
    "MLAB": {
        "name": "Mechanical Engineering Laboratory",
        "capacity": 30,
        "room_type": "lab",
    },
    "LR1": {
        "name": "Lecture Room 1",
        "capacity": 50,
        "room_type": "lecture_hall",
    },
    "LR2": {
        "name": "Lecture Room 2",
        "capacity": 50,
        "room_type": "lecture_hall",
    },
    "LR3": {
        "name": "Lecture Room 3",
        "capacity": 50,
        "room_type": "lecture_hall",
    },
}

# Patterns
_TIME_RANGE_PATTERN = re.compile(r"(\d{1,2})[:.]\d{2}\s*[-–]\s*(\d{1,2})[:.]\d{2}")
_HOUR_PATTERN = re.compile(r"^(\d{1,2})[:.]\d{2}$")
_COURSE_CODE_PATTERN = re.compile(r"^([A-Z]{2,4})\s+(\d{4})", re.IGNORECASE)
_GROUP_NOTATION_PATTERN = re.compile(r"\([^)]*\)")
_YEAR_PATTERN = re.compile(r"(\d)(?:ST|ND|RD|TH)?\s*YEAR", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TimetableParser:
    """
    Parse a university timetable PDF into structured data.

    Usage:
        parser = TimetableParser("/path/to/timetable.pdf")
        result = parser.parse()
        # result is a dict with keys: metadata, courses, time_slots, rooms
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._courses: List[Dict] = []
        self._time_slots: List[Dict] = []
        self._room_codes: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self) -> Dict:
        """
        Open the PDF and extract timetable data.

        Returns:
            dict with keys: metadata, courses, time_slots, rooms
        """
        logger.info("Opening PDF: %s", self.pdf_path)

        with pdfplumber.open(self.pdf_path) as pdf:
            logger.info("PDF has %d page(s)", len(pdf.pages))
            for page_number, page in enumerate(pdf.pages, start=1):
                self._process_page(page, page_number)

        result = {
            "metadata": {
                "term": "Term 1",
                "year": 2026,
                "school": "School of Engineering",
                "parsed_date": datetime.utcnow().isoformat() + "Z",
                "source_file": self.pdf_path,
            },
            "courses": self._deduplicate_courses(),
            "time_slots": self._time_slots,
            "rooms": self._format_rooms(),
        }

        logger.info(
            "Parse complete: %d courses, %d slots, %d rooms",
            len(result["courses"]),
            len(result["time_slots"]),
            len(result["rooms"]),
        )
        return result

    # ------------------------------------------------------------------
    # Page processing
    # ------------------------------------------------------------------

    def _process_page(self, page, page_number: int) -> None:
        """Extract day and timetable table from a single page."""
        raw_text = page.extract_text() or ""
        day = self._detect_day(raw_text)

        if day is None:
            # Some PDFs embed the day in graphics; fall back to table scan.
            day = self._detect_day_from_table(page)

        if day is None:
            logger.debug("Page %d: no day detected, skipping.", page_number)
            return

        logger.debug("Page %d: detected day %s", page_number, day)

        table = page.extract_table()
        if table:
            self._parse_table(table, day)
        else:
            # Try word-level extraction as a fallback
            words = page.extract_words()
            if words:
                self._parse_words_fallback(words, day)

    def _detect_day(self, text: str) -> Optional[str]:
        """Return the first day name found in page text."""
        upper = text.upper()
        for day in DAYS:
            if day in upper:
                return day
        return None

    def _detect_day_from_table(self, page) -> Optional[str]:
        """Scan table headers for a day name when text extraction fails."""
        table = page.extract_table()
        if not table:
            return None
        for row in table[:3]:  # Check first three rows only
            if not row:
                continue
            for cell in row:
                if not cell:
                    continue
                day = self._detect_day(cell)
                if day:
                    return day
        return None

    # ------------------------------------------------------------------
    # Table parsing
    # ------------------------------------------------------------------

    def _parse_table(self, table: List, day: str) -> None:
        """
        Parse a full timetable table extracted from one page.

        The first row is treated as a header row containing program/year labels.
        Subsequent rows contain time slots and course/room content per column.
        """
        if not table or len(table) < 2:
            return

        header_row = table[0]
        program_columns = self._identify_program_columns(header_row)

        if not program_columns:
            logger.debug(
                "Day %s: no program columns found in header. Header: %s",
                day, header_row
            )
            return

        for row in table[1:]:
            if not row:
                continue

            time_cell = row[0] if row else None
            if not time_cell:
                continue

            time_range = self._parse_time_range(str(time_cell))
            if not time_range:
                continue

            start_time, end_time = time_range

            for col_idx, (program, year) in program_columns.items():
                if col_idx >= len(row):
                    continue
                cell = row[col_idx]
                if cell and str(cell).strip():
                    self._parse_cell(
                        cell_text=str(cell),
                        day=day,
                        start_time=start_time,
                        end_time=end_time,
                        program=program,
                        year=year,
                    )

    def _identify_program_columns(self, header_row: List) -> Dict[int, Tuple[str, int]]:
        """
        Map column indices to (program_code, year_level) tuples.

        Returns only columns that match a known program and contain a year indicator.
        """
        columns: Dict[int, Tuple[str, int]] = {}

        for idx, cell in enumerate(header_row):
            if not cell:
                continue
            cell_upper = str(cell).upper()

            year_match = _YEAR_PATTERN.search(cell_upper)
            if not year_match:
                # Some headers use plain digits like "Y3" or "YEAR 3"
                digit_match = re.search(r"\bY(\d)\b|\bYEAR\s*(\d)\b", cell_upper)
                if not digit_match:
                    continue
                year = int(digit_match.group(1) or digit_match.group(2))
            else:
                year = int(year_match.group(1))

            for prog in PROGRAMS:
                if prog in cell_upper:
                    columns[idx] = (prog, year)
                    break

        return columns

    # ------------------------------------------------------------------
    # Cell parsing
    # ------------------------------------------------------------------

    def _parse_cell(
        self,
        cell_text: str,
        day: str,
        start_time: str,
        end_time: str,
        program: str,
        year: int,
    ) -> None:
        """
        Extract course code and room from a single grid cell.

        Cells typically contain:
            Line 1: Course code (e.g. "CEE 3111" or "EEE 5201 (D1, D3)")
            Line 2: Room code (e.g. "ENLT1")

        Multi-entry cells (two courses sharing a slot) are handled by
        splitting on blank lines or double newlines.
        """
        # Split into sub-entries separated by blank lines
        sub_entries = re.split(r"\n\s*\n", cell_text.strip())

        for entry in sub_entries:
            lines = [line.strip() for line in entry.strip().splitlines() if line.strip()]
            if not lines:
                continue

            raw_code = lines[0]
            room = lines[1] if len(lines) > 1 else "TBD"

            course_code = self._clean_course_code(raw_code)
            if not course_code:
                continue

            room_code = self._clean_room_code(room)

            self._courses.append({
                "code": course_code,
                "year": year,
                "program": program,
            })

            self._time_slots.append({
                "course_code": course_code,
                "day": day,
                "start_time": start_time,
                "end_time": end_time,
                "room": room_code,
                "groups": [f"{program} Year {year}"],
            })

            if room_code and room_code != "TBD":
                self._room_codes.add(room_code)

    # ------------------------------------------------------------------
    # Word-level fallback
    # ------------------------------------------------------------------

    def _parse_words_fallback(self, words: List[Dict], day: str) -> None:
        """
        Attempt basic extraction when table extraction fails.

        Groups words by vertical position (y-coordinate) and scans each
        line for course code patterns.
        """
        # Group words by approximate row (within 5pt tolerance)
        rows: Dict[int, List[str]] = {}
        for word in words:
            y_key = int(word.get("top", 0) / 5) * 5
            rows.setdefault(y_key, []).append(word.get("text", ""))

        current_time: Optional[Tuple[str, str]] = None

        for y_key in sorted(rows.keys()):
            line = " ".join(rows[y_key])
            time_range = self._parse_time_range(line)
            if time_range:
                current_time = time_range
                continue

            if not current_time:
                continue

            match = _COURSE_CODE_PATTERN.search(line)
            if match:
                program_candidate = match.group(1).upper()
                if program_candidate in PROGRAMS:
                    course_code = self._clean_course_code(match.group(0))
                    start_time, end_time = current_time
                    self._courses.append({"code": course_code, "year": 0, "program": program_candidate})
                    self._time_slots.append({
                        "course_code": course_code,
                        "day": day,
                        "start_time": start_time,
                        "end_time": end_time,
                        "room": "TBD",
                        "groups": [],
                    })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_time_range(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Extract (start_time, end_time) from a time range string.

        Accepts formats: "08:00 - 09:00", "08.00-09.00", "8:00–9:00"
        Also accepts single-hour cells like "08:00" and infers +1 hour end.
        """
        match = _TIME_RANGE_PATTERN.search(text)
        if match:
            start_h = int(match.group(1))
            end_h = int(match.group(2))
            return f"{start_h:02d}:00", f"{end_h:02d}:00"

        single = _HOUR_PATTERN.match(text.strip())
        if single:
            h = int(single.group(1))
            return f"{h:02d}:00", f"{h + 1:02d}:00"

        return None

    def _clean_course_code(self, raw: str) -> str:
        """
        Normalise a course code string.

        Removes:
        - Group notations: (D1, D3), (A), etc.
        - Asterisk markers: **, *
        - Leading/trailing whitespace
        """
        code = _GROUP_NOTATION_PATTERN.sub("", raw)
        code = code.replace("*", "").replace("\n", " ")
        code = " ".join(code.split()).strip().upper()

        # Validate it looks like a course code (e.g. "CEE 3111" or "MATH401")
        if not _COURSE_CODE_PATTERN.match(code):
            return ""
        return code

    def _clean_room_code(self, raw: str) -> str:
        """Normalise a room code to uppercase, stripped."""
        code = raw.strip().upper()
        # Remove trailing punctuation or extra text after a space
        code = code.split()[0] if code else "TBD"
        return code

    def _deduplicate_courses(self) -> List[Dict]:
        """Return unique courses by code, preserving first occurrence."""
        seen: Set[str] = set()
        unique: List[Dict] = []
        for course in self._courses:
            if course["code"] not in seen:
                seen.add(course["code"])
                unique.append(course)
        return unique

    def _format_rooms(self) -> List[Dict]:
        """Build room list with metadata for all identified room codes."""
        result: List[Dict] = []
        for code in sorted(self._room_codes):
            meta = ROOM_METADATA.get(code, {})
            result.append({
                "code": code,
                "name": meta.get("name", code),
                "capacity": meta.get("capacity", 50),
                "room_type": meta.get("room_type", "lecture_hall"),
            })
        return result
