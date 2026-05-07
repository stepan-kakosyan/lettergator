from django.apps import AppConfig


class LettersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "letters"

    def ready(self):
        # Import registers Django system checks for this app.
        from . import checks  # noqa: F401
        from . import signals  # noqa: F401
