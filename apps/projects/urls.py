from django.urls import path

from . import views

app_name = "projects"


urlpatterns = [
    path("", views.list_view, name="list"),
    path("new/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_add, name="category_add"),
    path("categories/<int:pk>/rename/", views.category_rename, name="category_rename"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("calendar/<int:year>/<int:month>/", views.calendar_view, name="calendar_at"),
    path("search/", views.search_view, name="search"),
    path("report/", views.report_view, name="report"),
    path("import/", views.import_form, name="import_form"),
    path("import/confirm/", views.import_confirm, name="import_confirm"),
    path("import/template/", views.import_template, name="import_template"),
    path("bulk-delete/", views.bulk_delete, name="bulk_delete"),

    # --- HTMX / action endpoints (detail page) ---
    path("<int:pk>/inline/status/edit/", views.status_edit, name="inline_status_edit"),
    path("<int:pk>/inline/status/show/", views.status_show, name="inline_status_show"),
    path("<int:pk>/inline/status/save/", views.status_save, name="inline_status_save"),
    path("<int:pk>/inline/priority/edit/", views.priority_edit, name="inline_priority_edit"),
    path("<int:pk>/inline/priority/show/", views.priority_show, name="inline_priority_show"),
    path("<int:pk>/inline/priority/save/", views.priority_save, name="inline_priority_save"),
    path("<int:pk>/inline/dates/edit/", views.dates_edit, name="inline_dates_edit"),
    path("<int:pk>/inline/dates/show/", views.dates_show, name="inline_dates_show"),
    path("<int:pk>/inline/dates/save/", views.dates_save, name="inline_dates_save"),
    path("<int:pk>/inline/budget/edit/", views.budget_edit, name="inline_budget_edit"),
    path("<int:pk>/inline/budget/show/", views.budget_show, name="inline_budget_show"),
    path("<int:pk>/inline/budget/save/", views.budget_save, name="inline_budget_save"),
    path("<int:pk>/inline/vendor/edit/", views.vendor_edit, name="inline_vendor_edit"),
    path("<int:pk>/inline/vendor/show/", views.vendor_show, name="inline_vendor_show"),
    path("<int:pk>/inline/vendor/save/", views.vendor_save, name="inline_vendor_save"),
    path("<int:pk>/note/", views.note_add, name="note_add"),
    path("note/<int:pk>/edit/", views.note_edit, name="note_edit"),
    path("note/<int:pk>/show/", views.note_show, name="note_show"),
    path("note/<int:pk>/save/", views.note_save, name="note_save"),
    path("note/<int:pk>/delete/", views.note_delete, name="note_delete"),
    path("note/<int:pk>/pin/", views.note_pin, name="note_pin"),
    path("<int:pk>/attachment/upload/", views.attachment_upload, name="attachment_upload"),
    path("attachment/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),
    path("attachment/<int:pk>/download/", views.attachment_download, name="attachment_download"),
    path("<int:pk>/raci/add/", views.raci_add, name="raci_add"),
    path("raci/<int:pk>/remove/", views.raci_remove, name="raci_remove"),
    path("<int:pk>/approval/add/", views.approval_add, name="approval_add"),
    path("<int:pk>/approval/edit/", views.approval_edit, name="approval_edit"),

    path("recurring/", views.recurring_list, name="recurring_list"),
    path("recurring/new/", views.recurring_create, name="recurring_create"),
    path("recurring/<int:pk>/edit/", views.recurring_edit, name="recurring_edit"),
    path("recurring/<int:pk>/toggle/", views.recurring_toggle, name="recurring_toggle"),
]
