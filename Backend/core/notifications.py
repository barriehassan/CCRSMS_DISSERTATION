from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

User = get_user_model()


# -------------------------------------------------
# INTERNAL HELPER
# -------------------------------------------------
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


# -------------------------------------------------
# CITIZEN NOTIFICATIONS
# -------------------------------------------------
def notify_citizen_complaint_created(complaint):
    """
    Complaint owner notification after creation
    """
    citizen_user = complaint.citizen

    subject = "Complaint Submitted Successfully"
    message = (
        f"Hi {citizen_user.first_name},\n\n"
        f"Your complaint titled \"{complaint.title}\" has been submitted successfully.\n\n"
        f"Status: {complaint.status}\n"
        f"Priority: {complaint.priority_level}\n\n"
        f"Thank you for using CCRSMS."
    )

    _send_email(citizen_user.email, subject, message)


def notify_citizen_complaint_updated(complaint, updated_by="SYSTEM"):
    """
    Notify citizen when their complaint is updated
    """
    citizen_user = complaint.citizen

    subject = "Complaint Update Notification"
    message = (
        f"Hi {citizen_user.first_name},\n\n"
        f"Your complaint titled \"{complaint.title}\" has been updated.\n\n"
        f"Updated by: {updated_by}\n"
        f"Current Status: {complaint.status}\n\n"
        f"Please log in to CCRSMS to view the full details."
    )

    _send_email(citizen_user.email, subject, message)


def notify_citizen_complaint_deleted(citizen_user, complaint_title: str):
    """
    Notify citizen after they delete their complaint.
    Note: we pass title as string because complaint may be deleted already.
    """
    subject = "Complaint Deleted"
    message = (
        f"Hi {citizen_user.first_name},\n\n"
        f"Your complaint titled \"{complaint_title}\" has been deleted successfully.\n\n"
        f"Thank you for using CCRSMS."
    )
    _send_email(citizen_user.email, subject, message)



# -------------------------------------------------
# STAFF (WARD-BASED) NOTIFICATIONS
# -------------------------------------------------
def notify_staff_complaint_created(complaint):
    """
    Notify STAFF users in the SAME ward as the citizen
    """
    citizen_user = complaint.citizen

    if not citizen_user.ward:
        return

    staff_users = User.objects.filter(
        user_type="STAFF",
        is_active=True,
        ward=citizen_user.ward
    )

    for staff_user in staff_users:
        subject = "New Complaint in Your Ward"
        message = (
            f"Hello {staff_user.first_name},\n\n"
            f"A new complaint has been submitted in your ward.\n\n"
            f"Title: {complaint.title}\n"
            f"Category: {complaint.category.category_name}\n"
            f"Priority: {complaint.priority_level}\n"
            f"Status: {complaint.status}\n\n"
            f"Please log in to the staff portal to review this complaint."
        )

        _send_email(staff_user.email, subject, message)


def notify_staff_complaint_updated(complaint, updated_by="CITIZEN"):
    """
    Notify STAFF users when a complaint in their ward is updated
    """
    citizen_user = complaint.citizen

    if not citizen_user.ward:
        return

    staff_users = User.objects.filter(
        user_type="STAFF",
        is_active=True,
        ward=citizen_user.ward
    )

    for staff_user in staff_users:
        subject = "Complaint Updated in Your Ward"
        message = (
            f"Hello {staff_user.first_name},\n\n"
            f"A complaint in your ward has been updated.\n\n"
            f"Title: {complaint.title}\n"
            f"Updated by: {updated_by}\n"
            f"Current Status: {complaint.status}\n\n"
            f"Please log in to the staff portal to view the update."
        )

        _send_email(staff_user.email, subject, message)
