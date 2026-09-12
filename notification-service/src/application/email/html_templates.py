from __future__ import annotations

from html import escape


def render_email_html(*, title: str, body_text: str, cta_url: str | None = None, cta_label: str = "Open") -> str:
    paragraphs = "".join(f"<p>{escape(part.strip())}</p>" for part in body_text.split("\n") if part.strip())
    cta = ""
    if cta_url:
        cta = f'<p><a href="{escape(cta_url)}" style="display:inline-block;padding:10px 16px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;">{escape(cta_label)}</a></p>'
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;line-height:1.5;color:#111;">
  <h2>{escape(title)}</h2>
  {paragraphs}
  {cta}
  <hr/>
  <p style="color:#666;font-size:12px;">AI Interview Tutor</p>
</body></html>"""


def template_for_email_type(email_type: str, *, subject: str, body: str) -> tuple[str, str]:
    """Return (subject, html_body) tuned per notification type."""
    mapping = {
        "email_verify": ("Verify your email", "Verify Email"),
        "welcome": ("Welcome to AI Interview Tutor", "Get Started"),
        "plan_ready": ("Your practice plan is ready", "View Plan"),
        "interview_complete": ("Interview complete — report ready", "View Report"),
    }
    title, cta = mapping.get(email_type, (subject, "Open"))
    html = render_email_html(title=title, body_text=body)
    return subject, html
