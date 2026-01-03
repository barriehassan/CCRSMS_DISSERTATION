from django.conf import settings
from django.core.mail import send_mail
from twilio.rest import Client


def send_welcome_email(to_email: str, first_name: str):
    if not to_email:
        return

    subject = "Welcome to CCRSMS"
    message = f"Hi {first_name}, your registration was successful."
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [to_email],
        fail_silently=False,
    )


def send_welcome_sms(to_phone: str, first_name: str):
    if not to_phone:
        return

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN,
    )

    message = f"Hi {first_name}, your CCRSMS account has been created successfully."

    client.messages.create(
        body=message,
        from_=settings.TWILIO_FROM_NUMBER,
        to=to_phone,  # +232XXXXXXXX
    )
