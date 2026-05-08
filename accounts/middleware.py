from django.utils import translation


class UserLanguageMiddleware:
    """
    For authenticated users who have a saved language preference,
    override whatever Django's LocaleMiddleware detected and activate
    the user's stored language instead.
    Runs after AuthenticationMiddleware so request.user is available.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and hasattr(request.user, "language")
            and request.user.language
        ):
            lang = request.user.language
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
        return self.get_response(request)
