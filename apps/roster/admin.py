from django.contrib import admin

from .models import RosterPerson


@admin.register(RosterPerson)
class RosterPersonAdmin(admin.ModelAdmin):
    list_display = ("name", "role_title", "email", "archived", "updated_at")
    list_filter = ("archived",)
    search_fields = ("name", "email", "role_title")
