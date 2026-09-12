from observability.pii import redact_text


def test_redact_email_and_bearer():
    text = "user@example.com Authorization: Bearer abc.def.ghi phone +12345678901"
    redacted = redact_text(text)
    assert "[REDACTED_EMAIL]" in redacted
    assert "Bearer ***" in redacted
    assert "[REDACTED_PHONE]" in redacted
