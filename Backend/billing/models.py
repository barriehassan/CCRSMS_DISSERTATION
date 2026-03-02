from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from accounts.models import Ward 

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

 # you already have this model


class WasteInterval(models.TextChoices):
    WEEK = "WEEK", "Weekly"
    MONTH = "MONTH", "Monthly"


class CoverageStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"


class WasteServiceProvider(models.Model):
    name = models.CharField(max_length=150, unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.name


class WasteBlock(models.Model):
    """
    FCC Blocks 1..8
    """
    block_number = models.PositiveSmallIntegerField(unique=True)  # 1..8
    name = models.CharField(max_length=50, blank=True)  # optional: "Block 1"

    def __str__(self):
        return self.name or f"Block {self.block_number}"


class WasteBlockProvider(models.Model):
    """
    Exactly one provider per block.
    """
    block = models.OneToOneField(WasteBlock, on_delete=models.CASCADE, related_name="provider_map")
    provider = models.ForeignKey(WasteServiceProvider, on_delete=models.CASCADE, related_name="blocks")

    def __str__(self):
        return f"{self.block} -> {self.provider}"


class WasteWardMeta(models.Model):
    """
    Keeps waste-related ward info without changing accounts.Ward.
    - code: numeric ward code like 399..446
    - block: which FCC block the ward belongs to
    """
    ward = models.OneToOneField(Ward, on_delete=models.CASCADE, related_name="waste_meta")
    code = models.PositiveIntegerField(null=True, blank=True)  # optional if your Ward.name already matches
    block = models.ForeignKey(WasteBlock, on_delete=models.SET_NULL, null=True, blank=True, related_name="ward_metas")

    def __str__(self):
        return f"{self.ward} (code={self.code}) -> {self.block}"


class WastePlan(models.Model):
    """
    Prices stored in NEW LEONES (SLE): weekly=25, monthly=100
    """
    name = models.CharField(max_length=50)  # Weekly / Monthly
    interval = models.CharField(max_length=10, choices=WasteInterval.choices)
    price = models.DecimalField(max_digits=12, decimal_places=2)  # SLE
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.price} SLE)"


class WasteCoverage(models.Model):
    """
    A paid coverage period for waste collection.
    Renewals extend from the last end_date if still active.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="waste_coverages")
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    block = models.ForeignKey(WasteBlock, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.ForeignKey(WasteServiceProvider, on_delete=models.SET_NULL, null=True, blank=True)
    plan = models.ForeignKey(WastePlan, on_delete=models.SET_NULL, null=True, blank=True)

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(max_length=10, choices=CoverageStatus.choices, default=CoverageStatus.ACTIVE)

    last_payment = models.ForeignKey("Payment", on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user} - {self.plan} - {self.status}"


class BusinessCategory(models.TextChoices):
    CONSUMER_STAPLE = "CONSUMER_STAPLE", "Consumer Staple"
    INDUSTRY_SERVICES = "INDUSTRY_SERVICES", "Industry / Services"
    FINANCIAL_SERVICES = "FINANCIAL_SERVICES", "Financial Services"
    HEALTH_EDUCATION = "HEALTH_EDUCATION", "Health / Education"
    HOSPITALITY = "HOSPITALITY", "Hospitality"
    OTHER = "OTHER", "Other"


class Business(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="businesses")
    business_name = models.CharField(max_length=200)
    category = models.CharField(max_length=40, choices=BusinessCategory.choices)
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    # optional: OARG reg info
    national_reg_number = models.CharField(max_length=80, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.business_name


class DemandNoticeStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"
    PAID = "PAID", "Paid"


class BusinessLicenseDemandNotice(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business_license_notices")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="demand_notices")

    notice_number = models.CharField(max_length=60)
    license_year = models.PositiveIntegerField()

    amount_due = models.DecimalField(max_digits=12, decimal_places=2)  # stored in SLE
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=DemandNoticeStatus.choices, default=DemandNoticeStatus.SUBMITTED)

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_business_license_notices"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.TextField(blank=True, null=True)

    # optional: link to the bill (so staff can open quickly)
    bill = models.OneToOneField("Bill", on_delete=models.SET_NULL, null=True, blank=True, related_name="business_license_notice")

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("notice_number", "license_year")

    def __str__(self):
        return f"RDN {self.notice_number} ({self.license_year}) - {self.status}"

