"""Verification code generation and email sending."""

import logging
import os
import secrets

logger = logging.getLogger(__name__)


def generate_code() -> str:
    """Generate a 6-digit verification code."""
    return str(secrets.randbelow(900000) + 100000)


async def send_verification_email(email: str, code: str) -> None:
    """Send verification code via SMTP. Falls back to logging in dev mode."""
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    if not smtp_host:
        logger.info(f"[DEV] Verification code for {email}: {code}")
        return

    import aiosmtplib
    import ssl
    from email.mime.text import MIMEText

    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    msg = MIMEText(
        f"您的 QuantGPT 验证码是：{code}\n\n验证码有效期 5 分钟，请勿泄露。",
        "plain",
        "utf-8",
    )
    msg["Subject"] = f"QuantGPT 验证码: {code}"
    msg["From"] = smtp_from
    msg["To"] = email

    tls_context = ssl.create_default_context()
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_NONE

    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_password,
        use_tls=use_tls,
        tls_context=tls_context,
    )
    logger.info(f"Verification email sent to {email}")
