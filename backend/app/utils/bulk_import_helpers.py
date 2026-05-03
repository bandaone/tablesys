"""
Shared utilities for bulk import (CSV/Excel) across all entity routers.

These helpers are tenant-agnostic — they read live departments from the
database and apply normalised fuzzy matching so any university's naming
conventions are resolved correctly without hardcoded department names.
"""

import difflib
import re
import pandas as pd


def normalize_text(text: str) -> str:
    """
    Normalise a department label for fuzzy comparison.
    - Lowercases
    - Replaces '&' with 'and'
    - Strips punctuation / special chars
    - Removes generic stop-words that add noise
    """
    t = str(text).lower().replace("&", "and").replace("-", " ")
    t = re.sub(r"[^a-z0-9\s]", "", t)
    stop_words = {
        "and", "of", "in", "the", "for", "a", "an",
        "engineering", "department", "faculty", "school",
        "college", "division", "institute", "center", "centre",
    }
    words = [w for w in t.split() if w not in stop_words]
    return " ".join(words)


def resolve_department_id(
    row: "pd.Series",
    departments: list,
    dept_id_map: dict,
    dept_code_map: dict,
    dept_name_map: dict,
    fuzzy_threshold: float = 0.60,
) -> "int | None":
    """
    Resolve a department ID from a spreadsheet row using a 3-stage cascade:

    1. Exact match on department_id column.
    2. Exact match on normalised department_code or department_name.
    3. Fuzzy match against every department's name AND code stored in the DB.
       The tenant's own departments are the only source of truth — fully dynamic.

    Returns the matched department ID or None if nothing matched.
    """

    # ── Stage 1: explicit numeric ID ──────────────────────────────────────────
    for col in ("department_id",):
        val = row.get(col)
        if val is not None and pd.notna(val):
            try:
                candidate = int(float(val))
                if candidate in dept_id_map:
                    return candidate
            except (ValueError, TypeError):
                pass

    # ── Stage 2: exact code / name match ──────────────────────────────────────
    code_val = row.get("department_code")
    if code_val is not None and pd.notna(code_val):
        code_str = str(code_val).strip().upper()
        if code_str in dept_code_map:
            return dept_code_map[code_str]

    name_val = row.get("department_name")
    if name_val is not None and pd.notna(name_val):
        name_str = str(name_val).strip().lower()
        if name_str in dept_name_map:
            return dept_name_map[name_str]

    # ── Stage 3: fuzzy / partial match (tenant-agnostic) ──────────────────────
    # Collect the raw text we have to work with
    raw = str(code_val or "").strip() or str(name_val or "").strip()
    # Also check a generic "department" fallback column
    if not raw or raw.lower() == "nan":
        raw = str(row.get("department", "")).strip()
    if not raw or raw.lower() == "nan":
        return None

    norm_raw = normalize_text(raw)
    if not norm_raw:
        return None

    best_id = None
    best_ratio = 0.0

    for dept in departments:
        norm_name = normalize_text(dept.name or "")
        norm_code = normalize_text(dept.code or "")

        ratio_name = difflib.SequenceMatcher(None, norm_raw, norm_name).ratio() if norm_name else 0.0
        ratio_code = difflib.SequenceMatcher(None, norm_raw, norm_code).ratio() if norm_code else 0.0

        # Bonus: if the raw text *contains* the dept code or vice-versa, boost score
        if norm_code and (norm_code in norm_raw or norm_raw in norm_code):
            ratio_code = max(ratio_code, 0.85)
        if norm_name and (norm_name in norm_raw or norm_raw in norm_name):
            ratio_name = max(ratio_name, 0.80)

        best_local = max(ratio_name, ratio_code)
        if best_local > best_ratio:
            best_ratio = best_local
            best_id = dept.id

    if best_ratio >= fuzzy_threshold and best_id is not None:
        return best_id

    return None


def ffill_department_columns(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Forward-fill department-related columns.
    Excel files often list the department once and leave subsequent rows blank.
    Also converts whitespace-only cells to NaN before filling.
    """
    dept_cols = ["department", "department_code", "department_name", "department_id"]
    for col in dept_cols:
        if col in df.columns:
            df[col] = df[col].replace(r"^\s*$", pd.NA, regex=True).ffill()
    return df


def normalize_column_names(df: "pd.DataFrame", aliases: dict) -> "pd.DataFrame":
    """
    Lowercase and strip all column headers, then apply alias mapping
    so user-friendly headers (e.g. 'Course Code') are mapped to
    internal names (e.g. 'code').
    """
    df.columns = [str(c).strip().lower() for c in df.columns]
    df.rename(columns=aliases, inplace=True)
    return df


def safe_int(val, default: int = 0) -> int:
    """Parse a possibly-NaN or string value to int, returning default on failure."""
    try:
        if pd.isna(val) or str(val).strip() == "":
            return default
        return int(float(val))
    except Exception:
        return default
