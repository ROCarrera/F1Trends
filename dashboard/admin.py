from django.contrib import admin
from .models import Constructor, Driver, Race, Season, Winner


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("year", "updated_at")
    search_fields = ("year",)


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ("season", "round", "race_name", "date")
    list_filter = ("season__year",)
    search_fields = ("race_name", "circuit_name")


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("driver_id", "given_name", "family_name", "code")
    search_fields = ("driver_id", "given_name", "family_name")


@admin.register(Constructor)
class ConstructorAdmin(admin.ModelAdmin):
    list_display = ("constructor_id", "name", "nationality")
    search_fields = ("constructor_id", "name")


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ("race", "driver", "constructor", "updated_at")
    list_filter = ("race__season__year", "constructor__name")
    search_fields = ("driver__family_name", "constructor__name", "race__race_name")
