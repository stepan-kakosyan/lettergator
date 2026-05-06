from django.urls import include, path

urlpatterns = [
    path("auth/", include("accounts.api_urls")),
    path("letters/", include("letters.api_urls")),
]
