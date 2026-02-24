from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("refresh", views.refresh_data, name="refresh"),
    path("predictions/", views.predictions, name="predictions"),
    path("legends/", views.legends, name="legends"),
    path("profiles/", views.profiles_index, name="profiles_index"),
    path("profiles/drivers/<str:driver_id>/", views.driver_profile, name="driver_profile"),
    path(
        "profiles/constructors/<str:constructor_id>/",
        views.constructor_profile,
        name="constructor_profile",
    ),
]
