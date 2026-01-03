from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from phonenumber_field.modelfields import PhoneNumberField
from .validators import validate_sierra_leone_number, validate_nin, validate_passport

# Create your models here.

# -------------------------------------------
# Custom User Manager
# -------------------------------------------
class UserManager(BaseUserManager):

    def create_user(self, email, phone_number, password=None, user_type="CITIZEN", **extra_fields):
        if not email and not phone_number:
            raise ValueError("User must have an email or phone number")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            phone_number=phone_number,
            user_type=user_type,
            **extra_fields
        )

        user.set_password(password)
        user.save(using= self._db)
        return user

    def create_superuser(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("user_type", "ADMIN")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email=email, phone_number=phone_number, password=password, **extra_fields)


# -------------------------------------------
# Base User Model
# -------------------------------------------
class Ward(models.Model):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    username = None

    USER_TYPES = [
        ("CITIZEN", "Citizen"),
        ("STAFF", "Council Staff"),
        ("ADMIN", "Administrator"),
    ]

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)

    email = models.EmailField(unique=True, null=True, blank=True)

    phone_number = PhoneNumberField(
        region="SL",
        validators=[validate_sierra_leone_number],
        unique=True,
        null=True,
        blank=True
    )

    nin = models.CharField(
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_nin]
    )

    passport_number = models.CharField(
        max_length=9,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_passport]
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="CITIZEN")
    ward = models.ForeignKey(Ward, on_delete=models.RESTRICT, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    objects = UserManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user_type})"


class BaseProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)


    class Meta:
        abstract = True


class CitizenProfile(BaseProfile):
    GENDER_CHOICES = [
        ("MALE", "Male"),
        ("FEMALE", "Female"),
    ]

    OCCUPATION_CHOICES = [
        ("EMPLOYED", "Employed"),
        ("UNEMPLOYED", "Unemployed"),
        ("STUDENT", "Student"),
    ]

    address = models.TextField(blank=True, null=True)
    DOB = models.DateField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    occupation = models.CharField(max_length=20, choices=OCCUPATION_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"Citizen Profile: {self.user.first_name}"


class Department(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class StaffProfile(BaseProfile):

    STAFF_ROLES = [
        ("FIELD_OFFICER", "Field Officer"),
        ("COUNCILOR", "Councilor"),
    ]

    role = models.CharField(max_length=30, choices=STAFF_ROLES, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True)
    status = models.CharField(max_length=20, default="active")
    last_login = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Staff Profile: {self.user.first_name} - {self.role}"


class AdminProfile(BaseProfile):

    ADMIN_ROLES = [
        ("DEPARTMENT HEAD", "Department Head"),
        ("SYSTEM SURPPORT", "System Surpport"),
    ]

    role = models.CharField(max_length=30, choices=ADMIN_ROLES, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True)
    status = models.CharField(max_length=20, default="active")

    def __str__(self):
        return f"Admin Profile: {self.user.first_name} - {self.role}"






