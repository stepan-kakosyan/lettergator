from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, SecondaryEmail


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    ordering = ("email",)
    list_display = (
        "email",
        "full_name",
        "email_verified",
        "is_staff",
        "is_active",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": ("full_name", "email_verified", "email_verified_at"),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "email_verified",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
    search_fields = ("email", "full_name")


@admin.register(SecondaryEmail)
class SecondaryEmailAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "created_at")
    search_fields = ("user__email", "email")
