from django.urls import path

from wagtail_personalisation.delivery import PersonalisationFragmentsView

app_name = "wagtail_personalisation_fragments"

urlpatterns = [
    path("<int:page_id>/", PersonalisationFragmentsView.as_view(), name="page"),
]
