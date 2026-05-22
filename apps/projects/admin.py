from django.contrib import admin

from .models import Project, ProjectCategory, Tag


@admin.register(ProjectCategory)
class ProjectCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    list_editable = ("display_order",)
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "status", "priority",
        "projected_completion_date", "is_recurring_template",
    )
    list_filter = ("status", "category", "priority", "is_recurring_template")
    search_fields = ("title", "description", "vendor_name")
    autocomplete_fields = ("category",)
    filter_horizontal = ("tags",)
