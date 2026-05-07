from django.contrib import admin

from .models import ContactTicket, ContactTicketComment, Letter


@admin.register(Letter)
class LetterAdmin(admin.ModelAdmin):
    list_display = ("sender_email", "recipient_email", "delivery_at", "is_delivered")
    list_filter = ("is_delivered", "delivery_at", "send_to_me")
    search_fields = ("sender_email", "recipient_email")


class ContactTicketCommentInline(admin.TabularInline):
    model = ContactTicketComment
    extra = 1
    can_delete = False
    fields = (
        "author_display",
        "message",
        "created_at",
    )
    readonly_fields = ("author_display", "created_at")

    def author_display(self, obj):
        if obj.author:
            return obj.author.email
        return "-"

    author_display.short_description = "Author"


@admin.register(ContactTicket)
class ContactTicketAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "email",
        "user",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("subject", "email", "message", "user__email")
    inlines = [ContactTicketCommentInline]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, ContactTicketComment) and not obj.author_id:
                obj.author = request.user
                obj.commenter_email = request.user.email or ""
                obj.is_admin_comment = True
            elif isinstance(obj, ContactTicketComment) and obj.author_id:
                if obj.author.is_staff:
                    obj.is_admin_comment = True
                    if not obj.commenter_email:
                        obj.commenter_email = obj.author.email or ""
            obj.save()
        formset.save_m2m()


@admin.register(ContactTicketComment)
class ContactTicketCommentAdmin(admin.ModelAdmin):
    list_display = (
        "ticket",
        "author",
        "commenter_email",
        "is_admin_comment",
        "created_at",
    )
    list_filter = ("is_admin_comment", "created_at")
    search_fields = (
        "ticket__subject",
        "commenter_email",
        "author__email",
        "message",
    )
    exclude = ("is_admin_comment", "commenter_email")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        if obj.author and obj.author.is_staff:
            obj.is_admin_comment = True
            obj.commenter_email = obj.author.email or ""
        super().save_model(request, obj, form, change)
