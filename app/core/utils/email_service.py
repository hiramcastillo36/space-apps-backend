from dataclasses import dataclass
from smtplib import SMTPException

from django.core.mail import send_mail
from django.conf import settings


@dataclass
class EmailContent:
    subject: str
    message: str
    to: str
    from_email: str


class EmailSender:
    def send(self, content: EmailContent):
        mail = send_mail(
            content.subject,
            content.message,
            content.from_email,
            [content.to],
            fail_silently=False,
        )

        if mail == 0:
            raise SMTPException("Email not sent")
        return mail


class EmailService:

    def __init__(self, sender):
        self.sender = sender

    def send_email(self, content: EmailContent):
        return self.sender.send(content)

    def send_reset_password_email(self, user, token):
        reset_url = f"{settings.FRONTEND_URL}/reset-password/?token={token}&email={user.email}" # noqa

        subject = "Password Reset Request"
        message = f"Hi {user.name},\n\nYou requested a password reset. Please click the link below to reset your password: \n{reset_url}\n\nIf you did not request this, please ignore this email." # noqa
        email_content = EmailContent(subject, message, user.email, "no-reply")
        return self.send_email(email_content)
