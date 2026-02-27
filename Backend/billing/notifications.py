from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.contrib.auth import get_user_model

User = get_user_model()


# ----------------------------
# INTERNAL HELPER
# ----------------------------
def _send_email(to_email: str, subject: str, message: str):
    if not to_email:
        return
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [to_email],
        fail_silently=False,
    )


def _service_label(service_type: str) -> str:
    # In case service_type is "LOCAL_TAX", show "Local Tax"
    return str(service_type).replace("_", " ").title()


# ----------------------------
# PAYMENT NOTIFICATIONS
# ----------------------------
# def notify_citizen_payment_success(payment, bill, user):
#     subject = f"Payment Successful - {_service_label(bill.service_type)}"
#     message = (
#         f"Hi {user.first_name},\n\n"
#         f"Your payment was successful.\n\n"
#         f"Service: {_service_label(bill.service_type)}\n"
#         f"Amount Paid: {payment.amount}\n"
#         f"Status: {payment.status}\n"
#         f"Date: {payment.paid_at}\n\n"
#         f"Thank you for using CCRSMS."
#     )
#     _send_email(user.email, subject, message)

def notify_citizen_payment_success(payment, bill, user):
    subject = "Payment Successful - Local Tax"
    message = (
        f"Hi {user.first_name} {user.last_name},\n\n"
        f"Your Local Tax payment was successful.\n"
        f"Amount: LE {int(bill.amount_due):,}\n"
        f"Date: {payment.paid_at}\n\n"
        f"Your receipt is attached.\n"
        f"Thank you."
    )

    email = EmailMessage(subject, message, settings.EMAIL_HOST_USER, [user.email])

    # ✅ Attach PDF if exists
    if payment.receipt_pdf:
        email.attach(payment.receipt_pdf.name, payment.receipt_pdf.read(), "application/pdf")

    email.send(fail_silently=False)


def notify_staff_ward_payment_success(payment, bill, user):
    """
    Notify STAFF/COUNCILOR users in same ward as the citizen.
    You already store staff/councilor under user_type="STAFF".
    """
    if not user.ward:
        return

    staff_users = User.objects.filter(
        user_type="STAFF",
        is_active=True,
        ward=user.ward
    )

    for staff_user in staff_users:
        subject = f"New Payment in Your Ward - {_service_label(bill.service_type)}"
        message = (
            f"Hello {staff_user.first_name},\n\n"
            f"A citizen in your ward has completed a payment.\n\n"
            f"Citizen: {user.first_name} {user.last_name}\n"
            f"Ward: {user.ward}\n"
            f"Service: {_service_label(bill.service_type)}\n"
            f"Amount: {payment.amount}\n"
            f"Paid At: {payment.paid_at}\n\n"
            f"Log in to the staff portal for more details."
        )
        _send_email(staff_user.email, subject, message)


def notify_admin_payment_success(payment, bill, user):
    """
    Notify ALL admins for every payment.
    """
    admin_users = User.objects.filter(user_type="ADMIN", is_active=True)

    for admin_user in admin_users:
        subject = f"Payment Received - {_service_label(bill.service_type)}"
        message = (
            f"Hello {admin_user.first_name},\n\n"
            f"A payment has been received.\n\n"
            f"Citizen: {user.first_name} {user.last_name}\n"
            f"Ward: {user.ward}\n"
            f"Service: {_service_label(bill.service_type)}\n"
            f"Amount: {payment.amount}\n"
            f"Paid At: {payment.paid_at}\n\n"
            f"Please review in the admin portal."
        )
        _send_email(admin_user.email, subject, message)