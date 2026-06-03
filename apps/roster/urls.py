from django.urls import path

from . import views, views_groups

app_name = "roster"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("new/", views.create, name="create"),
    # Groups (committees) — listed before <int:pk>/ patterns so the
    # literal segment matches first.
    path("groups/", views_groups.group_list, name="group_list"),
    path("groups/new/", views_groups.group_create, name="group_create"),
    path("groups/<int:pk>/", views_groups.group_detail, name="group_detail"),
    path("groups/<int:pk>/edit/", views_groups.group_edit, name="group_edit"),
    path("groups/<int:pk>/delete/", views_groups.group_delete, name="group_delete"),
    path("groups/<int:pk>/members/add/", views_groups.group_member_add,
         name="group_member_add"),
    path("groups/members/<int:pk>/remove/", views_groups.group_member_remove,
         name="group_member_remove"),

    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/archive/", views.archive, name="archive"),
    path("<int:pk>/unarchive/", views.unarchive, name="unarchive"),
]
