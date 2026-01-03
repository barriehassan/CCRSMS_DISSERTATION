from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()

# Register your models here.


admin.site.register(Ward)
admin.site.register(CitizenProfile)
admin.site.register(StaffProfile)
admin.site.register(AdminProfile)
admin.site.register(Department)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    # Since you removed username, remove it from fieldsets and forms
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "user_type", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone_number")

    # Fields shown on user edit page
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone_number", "ward", "nin", "passport_number")}),
        (_("Role"), {"fields": ("user_type",)}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    # Fields shown on “Add user” page in admin
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "phone_number", "user_type", "password1", "password2", "is_staff", "is_superuser"),
        }),
    )

    # Because username is removed:
    username_field = "email"


