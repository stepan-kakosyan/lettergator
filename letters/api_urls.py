from django.urls import path

from .api_views import (
    LetterDeliveryStatusApiView,
    LetterDetailApiView,
    LetterListCreateApiView,
)

urlpatterns = [
    path("", LetterListCreateApiView.as_view(), name="api-letters-list-create"),
    path("<int:letter_id>/", LetterDetailApiView.as_view(), name="api-letters-detail"),
    path(
        "<uuid:letter_id>/delivery-status/",
        LetterDeliveryStatusApiView.as_view(),
        name="api-letters-delivery-status",
    ),
]
