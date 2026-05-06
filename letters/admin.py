from django.contrib import admin

from .models import Letter


@admin.register(Letter)
class LetterAdmin(admin.ModelAdmin):
    list_display = ("sender_email", "recipient_email", "delivery_at", "is_delivered")
    list_filter = ("is_delivered", "delivery_at", "send_to_me")
    search_fields = ("sender_email", "recipient_email")
