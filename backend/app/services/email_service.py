from __future__ import annotations

import smtplib
from email.message import EmailMessage


class EmailService:
    def __init__(
        self,
        *,
        host: str | None,
        port: int,
        username: str | None,
        password: str | None,
        from_email: str | None,
        use_tls: bool,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def is_configured(self) -> bool:
        return bool(self.host and self.from_email)

    def send_otp(self, *, to_email: str, username: str, otp_code: str, expiry_minutes: int) -> None:
        if not self.is_configured():
            raise RuntimeError('SMTP is not configured.')

        message = EmailMessage()
        message['Subject'] = 'BiteBuddy Email Verification OTP'
        message['From'] = self.from_email
        message['To'] = to_email
        message.set_content(
            (
                f'Hi {username},\n\n'
                f'Your BiteBuddy verification code is: {otp_code}\n'
                f'This code expires in {expiry_minutes} minutes.\n\n'
                'If you did not request this, please ignore this email.'
            )
        )

        with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)
