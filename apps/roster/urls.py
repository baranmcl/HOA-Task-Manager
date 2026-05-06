from django.urls import path

from . import views

app_name = "roster"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("new/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/archive/", views.archive, name="archive"),
    path("<int:pk>/unarchive/", views.unarchive, name="unarchive"),
]
