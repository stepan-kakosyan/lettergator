from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import BalanceTransaction, CustomUser, LoginEvent, SecondaryEmail


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    ordering = ("email",)
    list_display = (
        "email",
        "full_name",
        "balance",
        "email_verified",
        "is_staff",
        "is_active",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "full_name",
                    "balance",
                    "email_verified",
                    "email_verified_at",
                ),
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


@admin.register(BalanceTransaction)
class BalanceTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "reason", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "reason")


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("user", "method", "logged_in_at")
    list_filter = ("method", "logged_in_at")
    search_fields = ("user__email",)
