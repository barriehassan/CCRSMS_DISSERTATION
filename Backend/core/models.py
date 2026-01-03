from django.contrib.gis.db import models
from django.conf import settings
from django.utils import timezone
from accounts.models import Department

# Create your models here.

# -------------------------------------
# 1. Complaint Category
# -------------------------------------
class ComplaintCategory(models.Model):
    category_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, related_name="categories")

    def __str__(self):
        return self.category_name


# -------------------------------------
# 2. Complaint Model (GeoDjango)
# -------------------------------------
class Complaint(models.Model):

    STATUS_CHOICES = [
        ("SUBMITTED", "Submitted"),
        ("ACKNOWLEDGED", "Acknowledged"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
        ("REJECTED", "Rejected"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]

    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="complaints"
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.CASCADE,
        related_name="complaints"
    )

    title = models.CharField(max_length=150)
    description = models.TextField()

    # Evidence - camera-captured image
    evidence_image = models.ImageField(
        upload_to="evidence/",
        null=True,
        blank=True
    )

    # Automatic geolocation capture (GeoDjango PointField)
    location = models.PointField(geography=True)

    # Optional reverse-geocoded fields
    street_name = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=255, blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="SUBMITTED",
        null=True,
        blank=True,
    )

    priority_level = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="LOW",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.citizen.first_name}"

