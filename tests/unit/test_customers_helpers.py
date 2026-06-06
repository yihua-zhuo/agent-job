"""Unit tests for the module-level helpers in src/api/routers/customers.py.

These are pure-function helpers (HTML sanitization, email validation) and are
not router endpoints, so they live in their own file to keep the router test
file scoped to endpoint behavior.
"""

from api.routers.customers import _is_valid_email, _sanitize


class TestSanitize:
    def test_strips_html_tags(self):
        assert _sanitize("<b>hello</b>") == "hello"

    def test_strips_nested_tags(self):
        assert _sanitize("<script>alert(1)</script>text") == "text"

    def test_removes_control_chars(self):
        result = _sanitize("hello\x00world")
        assert "\x00" not in result

    def test_strips_whitespace(self):
        assert _sanitize("  hello  ") == "hello"

    def test_empty_string_passthrough(self):
        assert _sanitize("") == ""

    def test_none_passthrough(self):
        assert _sanitize(None) is None

    def test_normal_string_unchanged(self):
        assert _sanitize("john doe") == "john doe"


class TestIsValidEmail:
    def test_valid_email(self):
        assert _is_valid_email("user@example.com") is True

    def test_valid_email_with_plus(self):
        assert _is_valid_email("user+tag@domain.co.uk") is True

    def test_missing_at_sign(self):
        assert _is_valid_email("userexample.com") is False

    def test_missing_domain(self):
        assert _is_valid_email("user@") is False

    def test_invalid_tld_too_short(self):
        assert _is_valid_email("user@domain.c") is False

    def test_empty_string(self):
        assert _is_valid_email("") is False
