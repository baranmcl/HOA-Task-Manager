from django.http import Http404
from django.urls import path

from . import views

app_name = "projects"


def _stub(request, *args, **kwargs):
    """Placeholder for endpoints wired by later tasks (13-16)."""
    raise Http404


urlpatterns = [
    path("", views.list_view, name="list"),
    path("new/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),

    # --- HTMX / action endpoints: stubbed here so detail.html renders;
    #     replaced with real views in Tasks 13-16. ---
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
    path("<int:pk>/note/", _stub, name="note_add"),
    path("<int:pk>/attachment/upload/", _stub, name="attachment_upload"),
    path("attachment/<int:pk>/delete/", _stub, name="attachment_delete"),
    path("attachment/<int:pk>/download/", _stub, name="attachment_download"),
    path("<int:pk>/raci/add/", _stub, name="raci_add"),
    path("raci/<int:pk>/remove/", _stub, name="raci_remove"),
    path("<int:pk>/approval/add/", _stub, name="approval_add"),
    path("<int:pk>/approval/edit/", _stub, name="approval_edit"),
]
