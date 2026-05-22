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
    path("<int:pk>/inline/status/edit/", _stub, name="inline_status_edit"),
    path("<int:pk>/inline/priority/edit/", _stub, name="inline_priority_edit"),
    path("<int:pk>/inline/dates/edit/", _stub, name="inline_dates_edit"),
    path("<int:pk>/inline/budget/edit/", _stub, name="inline_budget_edit"),
    path("<int:pk>/inline/vendor/edit/", _stub, name="inline_vendor_edit"),
    path("<int:pk>/note/", _stub, name="note_add"),
    path("<int:pk>/attachment/upload/", _stub, name="attachment_upload"),
    path("attachment/<int:pk>/delete/", _stub, name="attachment_delete"),
    path("attachment/<int:pk>/download/", _stub, name="attachment_download"),
    path("<int:pk>/raci/add/", _stub, name="raci_add"),
    path("raci/<int:pk>/remove/", _stub, name="raci_remove"),
    path("<int:pk>/approval/add/", _stub, name="approval_add"),
    path("<int:pk>/approval/edit/", _stub, name="approval_edit"),
]
