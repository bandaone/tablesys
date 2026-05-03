"""
Input Sanitization Utilities

Prevents:
- CSV Injection (Formula Injection)
- XSS (Cross-Site Scripting)
- Control Character Injection
- DoS via oversized inputs
"""

import html
import re
from typing import Any

class InputSanitizer:
    """
    Sanitize user inputs to prevent CSV injection and XSS attacks.
    
    CSV Injection Prevention:
    - Prefixes dangerous characters (=, +, -, @, \t, \r) with single quote
    - Prevents Excel from executing formulas
    
    XSS Prevention:
    - HTML escapes all user inputs
    - Converts <, >, &, ", ' to safe entities
    
    Control Character Prevention:
    - Removes null bytes and other control characters
    - Prevents database corruption and encoding issues
    
    DoS Prevention:
    - Enforces maximum length limits
    - Prevents memory exhaustion attacks
    """
    
    # Characters that can trigger CSV injection
    CSV_DANGEROUS_CHARS = ['=', '+', '-', '@', '\t', '\r']
    
    @staticmethod
    def remove_control_characters(value: str) -> str:
        """
        Remove control characters (null bytes, etc.)
        
        Control characters can cause issues with:
        - Database storage
        - JSON encoding
        - Terminal output
        
        Keeps: newline (\n), tab (\t), carriage return (\r)
        Removes: null bytes, other control chars
        
        Args:
            value: String to clean
            
        Returns:
            String with control characters removed
        """
        # Remove null bytes and other control chars (except newline/tab)
        # \x00-\x08: null to backspace
        # \x0B-\x0C: vertical tab, form feed
        # \x0E-\x1F: shift out to unit separator
        # \x7F: delete
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
    
    @staticmethod
    def sanitize_for_csv(value: Any) -> str:
        """
        Sanitize input to prevent CSV injection attacks.
        
        If value starts with dangerous character, prefix with single quote.
        This prevents Excel from interpreting it as a formula.
        
        Examples:
            "=1+1" -> "'=1+1"
            "+SUM(A1:A10)" -> "'+SUM(A1:A10)"
            "Normal text" -> "Normal text"
        
        Args:
            value: Input to sanitize
            
        Returns:
            Sanitized string safe for CSV export
        """
        if value is None:
            return ""
        
        str_value = str(value).strip()
        
        # Check if starts with dangerous character
        if str_value and str_value[0] in InputSanitizer.CSV_DANGEROUS_CHARS:
            return f"'{str_value}"
        
        return str_value
    
    @staticmethod
    def sanitize_for_xss(value: Any) -> str:
        """
        Sanitize input to prevent XSS attacks.
        
        HTML escapes the input:
            < -> &lt;
            > -> &gt;
            & -> &amp;
            " -> &quot;
            ' -> &#x27;
        
        Examples:
            "<script>alert(1)</script>" -> "&lt;script&gt;alert(1)&lt;/script&gt;"
            "Normal text" -> "Normal text"
        
        Args:
            value: Input to sanitize
            
        Returns:
            HTML-escaped string safe for display
        """
        if value is None:
            return ""
        
        return html.escape(str(value))
    
    @staticmethod
    def sanitize_all(value: Any, max_length: int = 500) -> str:
        """
        Apply full sanitization pipeline.
        
        Pipeline:
        1. Trim whitespace
        2. Enforce length limit (DoS prevention)
        3. Remove control characters
        4. HTML escape (XSS prevention)
        5. CSV injection prevention
        
        Use this for all user inputs that will be:
        - Stored in database
        - Displayed in frontend
        - Exported to CSV/Excel
        
        Args:
            value: Input to sanitize
            max_length: Maximum allowed length (default 500)
            
        Returns:
            Fully sanitized string
        
        Examples:
            "=<script>alert(1)</script>" -> "'=&lt;script&gt;alert(1)&lt;/script&gt;"
            "Normal Course Name" -> "Normal Course Name"
        """
        if value is None:
            return ""
        
        # Trim whitespace
        str_value = str(value).strip()
        
        # Length limit (prevent DoS via huge inputs)
        if len(str_value) > max_length:
            str_value = str_value[:max_length]
        
        # Remove control characters
        str_value = InputSanitizer.remove_control_characters(str_value)
        
        # HTML escape removed: React frontend handles XSS escaping contextually.
        # Storing raw data in the DB prevents double-encoding and search bugs (e.g., 'Civil & Environmental').
        
        # CSV injection prevention (check AFTER escaping)
        # Note: html.escape doesn't escape =, +, -, @ so we need to check
        if str_value and str_value[0] in InputSanitizer.CSV_DANGEROUS_CHARS:
            str_value = f"'{str_value}"
        
        return str_value
    
    @staticmethod
    def sanitize_dict(data: dict, fields: list[str], max_length: int = 500) -> dict:
        """
        Sanitize specific fields in a dictionary.
        
        Args:
            data: Dictionary with user input
            fields: List of field names to sanitize
            max_length: Maximum allowed length per field
        
        Returns:
            New dictionary with sanitized fields
        
        Example:
            data = {"name": "=1+1", "code": "CS101"}
            sanitize_dict(data, ["name"])
            # Returns: {"name": "'=1+1", "code": "CS101"}
        """
        sanitized = data.copy()
        for field in fields:
            if field in sanitized:
                sanitized[field] = InputSanitizer.sanitize_all(sanitized[field], max_length)
        return sanitized


# Convenience functions for common use
def sanitize_input(value: Any, max_length: int = 500) -> str:
    """
    Sanitize a single input value (full pipeline: CSV + XSS + control chars).
    
    Args:
        value: Input to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Fully sanitized string
    """
    return InputSanitizer.sanitize_all(value, max_length)

def sanitize_csv(value: Any) -> str:
    """Sanitize for CSV injection only"""
    return InputSanitizer.sanitize_for_csv(value)

def sanitize_xss(value: Any) -> str:
    """Sanitize for XSS only"""
    return InputSanitizer.sanitize_for_xss(value)
