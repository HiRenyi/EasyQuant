"""Tests for quantgpt/email_service.py — code generation and email templates."""


from quantgpt.email_service import (
    _email_wrapper,
    _get_smtp_config,
    _truncate,
    generate_code,
)


class TestGenerateCode:
    def test_length_is_six(self):
        for _ in range(100):
            code = generate_code()
            assert len(code) == 6

    def test_all_digits(self):
        for _ in range(50):
            assert generate_code().isdigit()

    def test_no_leading_zero(self):
        for _ in range(200):
            code = generate_code()
            assert int(code) >= 100000

    def test_codes_are_not_all_identical(self):
        codes = {generate_code() for _ in range(20)}
        assert len(codes) > 1


class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", 200) == "hello"

    def test_long_string_truncated(self):
        result = _truncate("a" * 300, 200)
        assert len(result) == 203
        assert result.endswith("...")

    def test_exact_boundary(self):
        assert _truncate("a" * 200, 200) == "a" * 200


class TestEmailWrapper:
    def test_contains_brand(self):
        html = _email_wrapper("<p>Test</p>")
        assert "QuantGPT" in html

    def test_contains_content(self):
        html = _email_wrapper("<p>Custom content</p>")
        assert "Custom content" in html

    def test_valid_html(self):
        html = _email_wrapper("<p>X</p>")
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html


class TestSmtpConfig:
    def test_returns_dict_with_expected_keys(self):
        cfg = _get_smtp_config()
        assert "host" in cfg
        assert "port" in cfg
        assert "user" in cfg
        assert "password" in cfg
        assert "from_addr" in cfg
        assert "use_tls" in cfg

    def test_port_is_int(self):
        cfg = _get_smtp_config()
        assert isinstance(cfg["port"], int)
