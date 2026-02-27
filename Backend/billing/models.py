from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.


class ServiceType(models.TextChoices):
    LOCAL_TAX = "LOCAL_TAX", "Local Tax"
    CITY_RATE = "CITY_RATE", "City Rate"
    WASTE_COLLECTION = "WASTE_COLLECTION", "Waste Collection"
    BUSINESS_LICENSE = "BUSINESS_LICENSE", "Business License"


class BillStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PARTIAL = "PARTIAL", "Partial"
    PAID = "PAID", "Paid"


class PaymentStatus(models.TextChoices):
    INITIATED = "INITIATED", "Initiated"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"


class Bill(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bills")
    service_type = models.CharField(max_length=30, choices=ServiceType.choices)

    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=10, choices=BillStatus.choices, default=BillStatus.PENDING)

    due_date = models.DateField(null=True, blank=True)

    allow_installments = models.BooleanField(default=False)
    max_installments = models.PositiveSmallIntegerField(default=1)
    installment_count = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.service_type} - {self.status}"


class Payment(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="payments")

    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.INITIATED)

    paid_at = models.DateTimeField(null=True, blank=True)

    # PDF receipt stored here
    receipt_pdf = models.FileField(upload_to="receipts/", null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Payment {self.id} - {self.bill.service_type} - {self.status}"
