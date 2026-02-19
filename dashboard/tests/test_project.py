from django.apps import apps
from django.contrib import admin
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from dashboard.models import Constructor, Driver, Race, Season, Winner
from dashboard.views import index, refresh_data


class ProjectWiringTests(SimpleTestCase):
    def test_dashboard_app_config(self) -> None:
        app_config = apps.get_app_config("dashboard")
        self.assertEqual(app_config.name, "dashboard")

    def test_urls_resolve_to_expected_views(self) -> None:
        self.assertEqual(resolve(reverse("dashboard:index")).func, index)
        self.assertEqual(resolve(reverse("dashboard:refresh")).func, refresh_data)
        self.assertEqual(resolve("/admin/").route, "admin/")

    def test_admin_models_are_registered(self) -> None:
        registry = admin.site._registry
        self.assertIn(Season, registry)
        self.assertIn(Race, registry)
        self.assertIn(Driver, registry)
        self.assertIn(Constructor, registry)
        self.assertIn(Winner, registry)

    def test_asgi_and_wsgi_entrypoints_load(self) -> None:
        from f1trends.asgi import application as asgi_application
        from f1trends.wsgi import application as wsgi_application

        self.assertIsNotNone(asgi_application)
        self.assertIsNotNone(wsgi_application)
