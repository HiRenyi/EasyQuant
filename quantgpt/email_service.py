"""Email sending service: verification codes, feedback notifications."""

import logging
import os
import secrets
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def generate_code() -> str:
    """Generate a 6-digit verification code."""
    return str(secrets.randbelow(900000) + 100000)


def _get_smtp_config():
    return {
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "port": int(os.environ.get("SMTP_PORT", "465")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() == "true",
    }


async def _send_email(to: str, subject: str, html_body: str) -> None:
    """Send an HTML email via SMTP. No-op if SMTP is not configured."""
    cfg = _get_smtp_config()
    if not cfg["host"]:
        logger.info(f"[DEV] Would send email to {to}: {subject}")
        return

    import aiosmtplib

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=cfg["host"],
        port=cfg["port"],
        username=cfg["user"],
        password=cfg["password"],
        use_tls=cfg["use_tls"],
    )
    logger.info(f"Email sent to {to}: {subject}")


async def send_verification_email(email: str, code: str) -> None:
    """Send verification code via SMTP. Falls back to logging in dev mode."""
    cfg = _get_smtp_config()
    if not cfg["host"]:
        logger.info(f"[DEV] Verification code for {email}: {code}")
        return

    import aiosmtplib

    msg = MIMEText(
        f"您的 QuantGPT 验证码是：{code}\n\n验证码有效期 5 分钟，请勿泄露。",
        "plain",
        "utf-8",
    )
    msg["Subject"] = f"QuantGPT 验证码: {code}"
    msg["From"] = cfg["from_addr"]
    msg["To"] = email

    await aiosmtplib.send(
        msg,
        hostname=cfg["host"],
        port=cfg["port"],
        username=cfg["user"],
        password=cfg["password"],
        use_tls=cfg["use_tls"],
    )
    logger.info(f"Verification email sent to {email}")


# --- Feedback email templates ---

def _truncate(text: str, max_len: int = 200) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text

_BRAND_COLOR = "#2563eb"
_BRAND_BG = "#f8fafc"

# EMAIL_TEMPLATES_PLACEHOLDER


def _email_wrapper(content: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:{_BRAND_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:520px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
  <div style="background:{_BRAND_COLOR};padding:20px 24px;">
    <span style="color:#fff;font-size:18px;font-weight:600;">QuantGPT</span>
  </div>
  <div style="padding:24px;">{content}</div>
  <div style="padding:16px 24px;border-top:1px solid #f1f5f9;color:#94a3b8;font-size:12px;">
    此邮件由 QuantGPT 自动发送，无需回复。
  </div>
</div>
</body></html>"""


async def send_feedback_received_email(email: str, feedback_id: str, description: str) -> None:
    """Send feedback received confirmation email."""
    desc_preview = _truncate(description)
    html = _email_wrapper(f"""
    <h2 style="margin:0 0 12px;font-size:16px;color:#1e293b;">收到你的反馈了</h2>
    <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px;">
      感谢你花时间告诉我们遇到的问题，每一条反馈都是我们变得更好的动力。
    </p>
    <div style="background:#f8fafc;border-left:3px solid {_BRAND_COLOR};padding:12px 16px;border-radius:0 8px 8px 0;margin:0 0 16px;">
      <p style="margin:0;color:#64748b;font-size:12px;">你的反馈内容</p>
      <p style="margin:4px 0 0;color:#334155;font-size:13px;">{desc_preview}</p>
    </div>
    <p style="color:#475569;font-size:14px;line-height:1.6;margin:0;">
      我们会尽快查看并处理，处理完成后会再次通知你。
    </p>""")
    await _send_email(email, "QuantGPT — 我们收到了你的反馈", html)


async def send_feedback_resolved_email(email: str, feedback_id: str, description: str) -> None:
    """Send feedback resolved notification email."""
    desc_preview = _truncate(description)
    html = _email_wrapper(f"""
    <h2 style="margin:0 0 12px;font-size:16px;color:#1e293b;">你的反馈已处理</h2>
    <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px;">
      你之前反馈的问题我们已经处理完成，感谢你帮助我们改进产品。
    </p>
    <div style="background:#f8fafc;border-left:3px solid #10b981;padding:12px 16px;border-radius:0 8px 8px 0;margin:0 0 16px;">
      <p style="margin:0;color:#64748b;font-size:12px;">原始反馈</p>
      <p style="margin:4px 0 0;color:#334155;font-size:13px;">{desc_preview}</p>
    </div>
    <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px;">
      欢迎回来试试看，如果还有其他想法或建议，随时告诉我们。
    </p>
    <a href="https://quantgpt.online" style="display:inline-block;background:{_BRAND_COLOR};color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:500;">
      打开 QuantGPT
    </a>""")
    await _send_email(email, "QuantGPT — 你的反馈已处理", html)
