from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("refresh", views.refresh_data, name="refresh"),
    path("predictions/", views.predictions, name="predictions"),
]
