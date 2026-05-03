"""
Tests for input sanitization utilities
"""

import pytest
from app.utils.sanitization import InputSanitizer, sanitize_input, sanitize_csv, sanitize_xss


class TestCSVInjectionPrevention:
    """Test CSV injection attack prevention"""
    
    def test_formula_injection_equals(self):
        """Test that = formulas are escaped"""
        assert sanitize_csv("=1+1") == "'=1+1"
        assert sanitize_csv("=SUM(A1:A10)") == "'=SUM(A1:A10)"
        result = sanitize_csv("=cmd|'/c calc.exe'")
        assert result.startswith("'=cmd|")
    
    def test_formula_injection_plus(self):
        """Test that + formulas are escaped"""
        assert sanitize_csv("+SUM(A1:A10)") == "'+SUM(A1:A10)"
        assert sanitize_csv("+1+1") == "'+1+1"
    
    def test_formula_injection_minus(self):
        """Test that - formulas are escaped"""
        assert sanitize_csv("-SUM(A1:A10)") == "'-SUM(A1:A10)"
        assert sanitize_csv("-1-1") == "'-1-1"
    
    def test_formula_injection_at(self):
        """Test that @ formulas are escaped"""
        assert sanitize_csv("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    
    def test_normal_text_unchanged(self):
        """Test that normal text is not modified"""
        assert sanitize_csv("Normal Text") == "Normal Text"
        assert sanitize_csv("123") == "123"
        assert sanitize_csv("Test Course") == "Test Course"


class TestXSSPrevention:
    """Test XSS attack prevention"""
    
    def test_script_tag_escaped(self):
        """Test that <script> tags are escaped"""
        result = sanitize_xss("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    def test_img_onerror_escaped(self):
        """Test that img onerror is escaped"""
        result = sanitize_xss('<img src=x onerror=alert(1)>')
        assert "onerror" in result  # Still present but escaped
        assert "&" in result  # HTML entities present
    
    def test_javascript_protocol_escaped(self):
        """Test that javascript: protocol is escaped"""
        result = sanitize_xss('<a href="javascript:alert(1)">Click</a>')
        assert "&" in result  # HTML escaped
    
    def test_event_handlers_escaped(self):
        """Test that event handlers are escaped"""
        result = sanitize_xss('<div onclick="alert(1)">Click</div>')
        assert "&" in result  # HTML escaped
    
    def test_normal_text_unchanged(self):
        """Test that normal text is unchanged"""
        result = sanitize_xss("Normal text")
        assert result == "Normal text"


class TestFullSanitization:
    """Test full sanitization pipeline"""
    
    def test_sanitize_input_csv_and_xss(self):
        """Test that sanitize_input handles both CSV and XSS"""
        result = sanitize_input("=<script>alert(1)</script>")
        assert result.startswith("'")  # CSV protection
        assert "&lt;" in result  # XSS protection
    
    def test_sanitize_input_normal_text(self):
        """Test that normal text passes through"""
        result = sanitize_input("Normal Course Name")
        assert "Normal Course Name" in result
    
    def test_sanitize_input_length_limit(self):
        """Test that length limit is enforced"""
        long_string = "A" * 1000
        result = sanitize_input(long_string, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_input_empty_string(self):
        """Test empty string handling"""
        assert sanitize_input("") == ""
    
    def test_sanitize_input_none(self):
        """Test None handling"""
        assert sanitize_input(None) == ""


class TestInputSanitizerClass:
    """Test InputSanitizer class methods"""
    
    def test_sanitize_for_csv(self):
        """Test CSV sanitization method"""
        assert InputSanitizer.sanitize_for_csv("=1+1") == "'=1+1"
        assert InputSanitizer.sanitize_for_csv("Normal") == "Normal"
    
    def test_sanitize_for_xss(self):
        """Test XSS sanitization method"""
        result = InputSanitizer.sanitize_for_xss("<script>alert(1)</script>")
        assert "&lt;script&gt;" in result
    
    def test_sanitize_all(self):
        """Test full sanitization pipeline"""
        result = InputSanitizer.sanitize_all("=<script>alert(1)</script>")
        assert result.startswith("'")
        assert "&lt;" in result
    
    def test_sanitize_dict(self):
        """Test dictionary sanitization"""
        data = {
            "name": "=SUM(A1)",
            "description": "Normal text",
            "code": "CS101"
        }
        result = InputSanitizer.sanitize_dict(data, ["name", "description"])
        assert result["name"].startswith("'")
        assert "Normal text" in result["description"]
        assert result["code"] == "CS101"  # Not sanitized (not in fields list)
    
    def test_remove_control_characters(self):
        """Test control character removal"""
        result = InputSanitizer.remove_control_characters("Test\x00String\x1F")
        assert "\x00" not in result
        assert "\x1F" not in result
        assert "TestString" in result


class TestEdgeCases:
    """Test edge cases and special scenarios"""
    
    def test_empty_string(self):
        """Test empty string handling"""
        assert sanitize_csv("") == ""
        assert sanitize_xss("") == ""
    
    def test_none_value(self):
        """Test None value handling"""
        assert sanitize_csv(None) == ""
        assert sanitize_xss(None) == ""
    
    def test_unicode_characters(self):
        """Test unicode character handling"""
        result = sanitize_input("Test™ ©")
        assert "Test" in result
    
    def test_mixed_formula_and_text(self):
        """Test mixed formula and normal text"""
        result = sanitize_csv("Normal =SUM(A1)")
        # Doesn't start with dangerous char, so not escaped
        assert result == "Normal =SUM(A1)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
