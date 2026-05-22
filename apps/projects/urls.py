from django.http import Http404
from django.urls import path

from . import views

app_name = "projects"


def _stub(request, *args, **kwargs):
    """Placeholder for list/detail until Tasks 11-12 wire the real views."""
    raise Http404


urlpatterns = [
    path("", views.list_view, name="list"),
    path("new/", views.create, name="create"),
    path("<int:pk>/", _stub, name="detail"),     # real view: Task 12
    path("<int:pk>/edit/", views.edit, name="edit"),
]
