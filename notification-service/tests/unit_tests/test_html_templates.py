from src.application.email.html_templates import render_email_html, template_for_email_type


def test_render_email_html_redacts_script():
    html = render_email_html(title="Hi", body_text="Hello\nWorld")
    assert "<p>Hello</p>" in html
    assert "<h2>Hi</h2>" in html


def test_template_for_email_type_verify():
    subject, html = template_for_email_type("email_verify", subject="Verify", body="Click link")
    assert subject == "Verify"
    assert "Verify your email" in html or "Click link" in html
