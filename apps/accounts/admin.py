from django.contrib import admin

from .models import BackupLog, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ("run_date", "finished_at", "bytes_uploaded", "object_key", "error")
    readonly_fields = (
        "run_date", "started_at", "finished_at", "bytes_uploaded", "object_key", "error",
    )
    ordering = ("-run_date",)
