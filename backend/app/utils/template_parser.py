"""
Structural Timetable Template Parser
=====================================

Reads a school's existing blank Word (.docx) or Excel (.xlsx) timetable
template and extracts its structural layout as a list of "slot containers".

A "slot container" is a cell (or merged group of cells) in the template
where the coordinator has written **Lecture**, **Lab**, **Tutorial**,
or **Practical**.

The parser returns:
  - ``shape``: Metadata describing the table structure (axes, headers).
  - ``containers``: List of TemplateContainer dicts, each representing
    one schedulable block.

This output is saved as a ``TemplateProfile`` in the database so that:
  1. The timetable generator can use containers as hard placement constraints.
  2. The exporter can "paint" generated results back into the original file.

Usage::
    # Excel
    parser = StructuralTemplateParser("path/to/template.xlsx", file_type="xlsx")
    result = parser.parse()

    # Word
    parser = StructuralTemplateParser("path/to/template.docx", file_type="docx")
    result = parser.parse()

    result["shape"]       # axis / header metadata
    result["containers"]  # list of TemplateContainer dicts
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAYS_UPPER = [d.upper() for d in DAYS]

# Keywords that mark a cell as a schedulable session.
# The parser does a case-insensitive search for these words.
SESSION_KEYWORDS: Dict[str, str] = {
    "lecture":   "lecture",
    "lect":      "lecture",
    "lab":       "practical",
    "practical": "practical",
    "prac":      "practical",
    "tutorial":  "tutorial",
    "tut":       "tutorial",
}

# Pattern for extracting hours like "07:00", "08.00", "7:00 - 8:00"
_TIME_PATTERN = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

def make_container(
    day: str,
    start_hour: int,
    end_hour: int,
    session_type: str,
    group_label: str,
    col_index: int,
    row_index: int,
    duration: int,
) -> Dict:
    """Return a standardized TemplateContainer dict."""
    return {
        "day": day,                    # "Monday"
        "start_hour": start_hour,      # 8  (= 08:00)
        "end_hour": end_hour,          # 10 (= 10:00)
        "duration": duration,          # hours
        "session_type": session_type,  # "lecture" | "practical" | "tutorial"
        "group_label": group_label,    # e.g. "AEN-3", "MEC-5", "GEN-2"
        "col_index": col_index,        # original column index in the file
        "row_index": row_index,        # original row index in the file
    }


# ---------------------------------------------------------------------------
# Main Parser
# ---------------------------------------------------------------------------

class StructuralTemplateParser:
    """
    Parse a blank structural timetable template (Word or Excel) and extract
    its layout as a list of schedulable containers.

    Parameters
    ----------
    file_path : str
        Absolute path to the template file.
    file_type : str
        ``"docx"`` or ``"xlsx"``.
    """

    def __init__(self, file_path: str, file_type: str):
        self.file_path = file_path
        self.file_type = file_type.lower().strip(".")
        if self.file_type not in ("docx", "xlsx", "xls", "csv"):
            raise ValueError(f"Unsupported file type: {self.file_type}. Use docx or xlsx.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self) -> Dict:
        """
        Parse the template and return a dict with:
        - ``shape``: axis metadata (time_col_index, header_rows, etc.)
        - ``containers``: list of TemplateContainer dicts
        """
        logger.info("Parsing template: %s (%s)", self.file_path, self.file_type)

        if self.file_type == "docx":
            return self._parse_docx()
        else:
            return self._parse_excel()

    # ------------------------------------------------------------------
    # Excel / CSV parsing
    # ------------------------------------------------------------------

    def _parse_excel(self) -> Dict:
        """Parse an Excel (.xlsx/.xls) or CSV file."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required. Run: pip install pandas openpyxl")

        if self.file_type == "csv":
            df = pd.read_csv(self.file_path, header=None, dtype=str)
        else:
            df = pd.read_excel(self.file_path, header=None, dtype=str)

        df = df.fillna("")

        rows = df.values.tolist()
        containers, shape = self._extract_from_row_matrix(rows, source="excel")

        return {
            "source": self.file_path,
            "file_type": self.file_type,
            "shape": shape,
            "containers": containers,
        }

    # ------------------------------------------------------------------
    # Word (.docx) parsing
    # ------------------------------------------------------------------

    def _parse_docx(self) -> Dict:
        """Parse a Word document. Reads all tables inside the document."""
        try:
            from docx import Document
            from docx.oxml.ns import qn
        except ImportError:
            raise ImportError("python-docx is required. Run: pip install python-docx")

        doc = Document(self.file_path)
        all_containers: List[Dict] = []
        combined_shape: Optional[Dict] = None

        for table_idx, table in enumerate(doc.tables):
            logger.debug("Processing docx table %d (%d rows)", table_idx, len(table.rows))
            rows = self._docx_table_to_matrix(table)
            containers, shape = self._extract_from_row_matrix(rows, source=f"docx_table_{table_idx}")
            all_containers.extend(containers)
            if combined_shape is None and shape:
                combined_shape = shape

        return {
            "source": self.file_path,
            "file_type": self.file_type,
            "shape": combined_shape or {},
            "containers": all_containers,
        }

    def _docx_table_to_matrix(self, table) -> List[List[str]]:
        """
        Convert a python-docx Table to a 2D list of strings by reading the
        underlying XML directly.

        We bypass ``row.cells`` intentionally — python-docx's high-level
        ``row_cells()`` can raise ``IndexError`` on tables with complex or
        non-standard merge patterns (e.g. nested merges, jagged grids).

        Instead we walk ``w:tr`` / ``w:tc`` elements ourselves:
          - each ``w:tc`` contributes one cell
          - ``w:gridSpan`` tells us how many columns the cell covers
          - we expand each cell text once per column it spans
        """
        from docx.oxml.ns import qn

        matrix: List[List[str]] = []

        for tr in table._tbl.findall(qn("w:tr")):
            row_data: List[str] = []

            for tc in tr.findall(qn("w:tc")):
                # Collect all text runs inside this cell
                text = "".join(
                    node.text or ""
                    for node in tc.iter(qn("w:t"))
                ).strip()

                # Determine how many grid columns this cell spans
                span = 1
                tcPr = tc.find(qn("w:tcPr"))
                if tcPr is not None:
                    gs = tcPr.find(qn("w:gridSpan"))
                    if gs is not None:
                        try:
                            span = int(gs.get(qn("w:val"), 1))
                        except (TypeError, ValueError):
                            span = 1

                # Repeat the text once per spanned column
                for _ in range(span):
                    row_data.append(text)

            if row_data:  # skip empty / structural rows
                matrix.append(row_data)

        # Normalise row lengths (safety net for malformed tables)
        max_len = max((len(r) for r in matrix), default=0)
        for row in matrix:
            while len(row) < max_len:
                row.append("")

        return matrix


    # ------------------------------------------------------------------
    # Core extraction (shared between docx and excel)
    # ------------------------------------------------------------------

    def _extract_from_row_matrix(
        self, rows: List[List[str]], source: str = ""
    ) -> Tuple[List[Dict], Dict]:
        """
        Core layout analysis. Accepts a 2D list of strings and returns
        (containers, shape).

        Algorithm
        ---------
        1. Find the "time column" (column 0 usually) by looking for cells
           that contain time-like strings (07:00, 08:00 …).
        2. Find the "header rows" that contain group labels (AEN, CEE, …).
        3. For each header cell, try to extract a group label and year.
        4. Walk down each content column:
           a. Match the row to a time from the time column.
           b. If the cell text matches a SESSION_KEYWORD, record a container.
        """
        if not rows:
            return [], {}

        # Step 1: Detect the time column index and time mapping (row_idx -> hour)
        time_col_index, time_map = self._detect_time_column(rows)

        # Step 2: Detect header rows and build a column → group_label mapping
        header_row_indices, col_group_map = self._detect_headers(rows, time_col_index)

        shape = {
            "time_col_index": time_col_index,
            "header_row_indices": header_row_indices,
            "col_group_map": col_group_map,
            "total_rows": len(rows),
            "total_cols": max((len(r) for r in rows), default=0),
            "source": source,
        }

        logger.debug(
            "[%s] time_col=%d, headers=%s, groups=%s",
            source, time_col_index, header_row_indices, col_group_map,
        )

        # Step 3: Collect current day (look for DAY name in first cell of any row)
        containers: List[Dict] = []
        current_day: str = DAYS[0]  # default to Monday if no day label found

        for row_idx, row in enumerate(rows):
            if row_idx in header_row_indices:
                continue

            # Check if this row announces a new day — update current_day but
            # do NOT skip yet.  Many templates put the day name AND the first
            # time slot on the same row, e.g. "MONDAY | 08:00-10:00 | Lecture".
            # Skipping the row (old behaviour) would lose all sessions on it.
            row_day = self._detect_day_in_row(row)
            if row_day:
                current_day = row_day

            # Get the time for this row — if there is none it is a pure
            # day-label / separator row and we can safely skip it.
            hour_info = time_map.get(row_idx)
            if hour_info is None:
                continue

            start_hour = hour_info["start"]
            end_hour   = hour_info["end"]

            # Walk columns
            for col_idx, cell_text in enumerate(row):
                if col_idx == time_col_index:
                    continue
                if col_idx not in col_group_map:
                    continue

                session_type = self._classify_session(cell_text)
                if session_type is None:
                    continue

                group_label = col_group_map[col_idx]
                duration = end_hour - start_hour

                container = make_container(
                    day=current_day,
                    start_hour=start_hour,
                    end_hour=end_hour,
                    session_type=session_type,
                    group_label=group_label,
                    col_index=col_idx,
                    row_index=row_idx,
                    duration=duration,
                )
                containers.append(container)
                logger.debug(
                    "Found container: day=%s hour=%d-%d type=%s group=%s",
                    current_day, start_hour, end_hour, session_type, group_label,
                )

        logger.info("[%s] Extracted %d containers", source, len(containers))
        return containers, shape

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _detect_time_column(
        self, rows: List[List[str]]
    ) -> Tuple[int, Dict[int, Dict]]:
        """
        Identify which column contains the time axis and build a mapping
        from row_index → {"start": int, "end": int}.

        Returns (time_col_index, time_map).
        """
        # Count how many time-like values each column has
        col_time_counts: Dict[int, int] = {}
        n_cols = max((len(r) for r in rows), default=0)

        for row in rows:
            for col_idx, cell in enumerate(row):
                if _TIME_PATTERN.search(str(cell)):
                    col_time_counts[col_idx] = col_time_counts.get(col_idx, 0) + 1

        if not col_time_counts:
            return 0, {}

        time_col_index = max(col_time_counts, key=col_time_counts.get)

        # Build the time map
        time_map: Dict[int, Dict] = {}
        for row_idx, row in enumerate(rows):
            # Guard: row must be long enough to contain the time column
            if time_col_index >= len(row):
                continue
            cell = str(row[time_col_index])
            parsed = self._parse_time_range(cell)
            if parsed:
                time_map[row_idx] = {"start": parsed[0], "end": parsed[1]}

        return time_col_index, time_map

    def _detect_headers(
        self, rows: List[List[str]], time_col_index: int
    ) -> Tuple[List[int], Dict[int, str]]:
        """
        Identify header rows and build col_index → group_label mapping.

        A header row is one where at least one non-time cell contains
        a year marker (2nd, 3rd, 4th, 5th, Year 2, Y3…) or a dept code.
        """
        header_row_indices: List[int] = []
        col_group_map: Dict[int, str] = {}

        # Patterns for group detection
        year_pattern = re.compile(
            r"(?:(\d)(?:st|nd|rd|th)?\s*year|year\s*(\d)|Y(\d)\b)", re.IGNORECASE
        )
        dept_codes = ["AEN", "CEE", "EEE", "GEE", "MEC", "GEN", "LAW",
                      "MED", "BIO", "CHEM", "PHYS", "CS", "IT", "BBA"]

        # We'll check only the first few rows for headers
        for row_idx, row in enumerate(rows[:8]):
            has_year_or_dept = False
            candidate_labels: Dict[int, str] = {}

            for col_idx, cell in enumerate(row):
                if col_idx == time_col_index:
                    continue
                cell_str = str(cell).strip()
                if not cell_str:
                    continue

                year_match = year_pattern.search(cell_str)
                year = None
                if year_match:
                    # Any of the three capture groups may be None
                    raw = year_match.group(1) or year_match.group(2) or year_match.group(3)
                    if raw is not None:
                        try:
                            year = int(raw)
                        except (TypeError, ValueError):
                            year = None
                    has_year_or_dept = year is not None

                # Look for dept code
                code_found = None
                upper = cell_str.upper()
                for code in dept_codes:
                    if code in upper:
                        code_found = code
                        has_year_or_dept = True
                        break

                # Build group label: prefer "AEN-3" style, else "Year 3" or just dept
                label = None
                if code_found and year:
                    label = f"{code_found}-{year}"
                elif code_found:
                    label = code_found
                elif year:
                    label = f"Year-{year}"

                if label:
                    candidate_labels[col_idx] = label

            if has_year_or_dept:
                header_row_indices.append(row_idx)
                col_group_map.update(candidate_labels)

        # If we still have columns with no group label (because the dept was on
        # a different row than the year), do a second pass merging across header rows
        if header_row_indices:
            col_group_map = self._merge_header_info(rows, header_row_indices, time_col_index, dept_codes)

        return header_row_indices, col_group_map

    def _merge_header_info(
        self,
        rows: List[List[str]],
        header_row_indices: List[int],
        time_col_index: int,
        dept_codes: List[str],
    ) -> Dict[int, str]:
        """
        Merge information from multiple header rows into a single col→label map.
        Common pattern: Row 0 has year groups ("2ND YEAR", "3RD YEAR"),
        Row 1 has dept codes ("AEN", "CEE", "EEE", …).
        """
        year_pattern = re.compile(
            r"(?:(\d)(?:st|nd|rd|th)?\s*year|year\s*(\d)|Y(\d)\b)", re.IGNORECASE
        )

        col_years: Dict[int, int] = {}
        col_depts: Dict[int, str] = {}

        for row_idx in header_row_indices:
            row = rows[row_idx]
            for col_idx, cell in enumerate(row):
                if col_idx == time_col_index:
                    continue
                cell_str = str(cell).strip()
                if not cell_str:
                    continue

                # Years
                ym = year_pattern.search(cell_str)
                if ym:
                    raw = ym.group(1) or ym.group(2) or ym.group(3)
                    if raw is not None:
                        try:
                            col_years[col_idx] = int(raw)
                        except (TypeError, ValueError):
                            pass

                # Depts
                upper = cell_str.upper()
                for code in dept_codes:
                    if code in upper and col_idx not in col_depts:
                        col_depts[col_idx] = code
                        break

        # Combine: if a column has a dept but no year, try to inherit year from
        # the nearest year-column to the left (common in merged-cell headers).
        merged: Dict[int, str] = {}
        last_year: Optional[int] = None

        all_cols = sorted(set(list(col_depts.keys()) + list(col_years.keys())))
        for col_idx in all_cols:
            year = col_years.get(col_idx)
            dept = col_depts.get(col_idx)

            if year:
                last_year = year
            if dept and last_year:
                merged[col_idx] = f"{dept}-{last_year}"
            elif dept:
                merged[col_idx] = dept
            elif year:
                merged[col_idx] = f"Year-{year}"

        return merged

    def _detect_day_in_row(self, row: List[str]) -> Optional[str]:
        """Return the day name if any cell in this row contains one."""
        for cell in row:
            upper = str(cell).upper().strip()
            for day_upper, day_title in zip(DAYS_UPPER, DAYS):
                # Use full word match to avoid "WEDNESDAY" matching "WED"
                if re.search(rf"\b{day_upper}\b", upper):
                    return day_title
        return None

    def _classify_session(self, cell_text: str) -> Optional[str]:
        """
        Return the canonical session type if the cell text contains a
        session keyword, otherwise return None.
        """
        lower = str(cell_text).lower().strip()
        if not lower:
            return None
        for keyword, session_type in SESSION_KEYWORDS.items():
            if re.search(rf"\b{re.escape(keyword)}\b", lower):
                return session_type
        return None

    def _parse_time_range(self, text: str) -> Optional[Tuple[int, int]]:
        """
        Extract (start_hour, end_hour) as integers from a time string.

        Handles:
        - "07:00 - 08:00", "07.00-08.00"
        - "07:00 -- 09:00" (blocks spanning multiple hours)
        - "07:00" (single time, assume 1-hour block)
        """
        matches = _TIME_PATTERN.findall(str(text))
        if len(matches) >= 2:
            start_h = int(matches[0][0])
            end_h = int(matches[-1][0])
            # Sanity check
            if 6 <= start_h < end_h <= 22:
                return start_h, end_h
        elif len(matches) == 1:
            h = int(matches[0][0])
            if 6 <= h <= 21:
                return h, h + 1
        return None
