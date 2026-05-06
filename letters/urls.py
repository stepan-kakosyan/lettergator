from django.urls import path

from .views import (
    concept_page,
    create_letter_page,
    dashboard_view,
    delete_letter_view,
    edit_letter_view,
    how_page,
    landing_page,
    letters_page,
    privacy_page,
)

urlpatterns = [
    path("", landing_page, name="landing-page"),
    path("letters/", letters_page, name="letters-page"),
    path("letters/create/", create_letter_page, name="letter-create-page"),
    path("letters/<int:letter_id>/delete/", delete_letter_view, name="letter-delete"),
    path("letters/<int:letter_id>/edit/", edit_letter_view, name="letter-edit"),
    path("vault/", letters_page, name="vault-page"),
    path("how/", how_page, name="how-page"),
    path("concept/", concept_page, name="concept-page"),
    path("privacy/", privacy_page, name="privacy-page"),
    path("dashboard/", dashboard_view, name="dashboard_view"),
]
