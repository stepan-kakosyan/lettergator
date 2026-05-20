
from django.contrib import admin
from django.urls import include, path
from . import pwa_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("lettergator_backend.api_urls")),
    path("accounts/", include("accounts.urls")),
    path("", include("letters.urls")),
    path("manifest.webmanifest", pwa_views.manifest, name="manifest"),
    path("service-worker.js", pwa_views.service_worker, name="service-worker"),
    path("offline/", pwa_views.offline, name="offline"),
]
