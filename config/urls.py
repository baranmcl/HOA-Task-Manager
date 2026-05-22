from django.contrib import admin
from django.urls import include, path

from apps.projects.views.dashboard import dashboard

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("roster/", include("apps.roster.urls", namespace="roster")),
    path("projects/", include("apps.projects.urls", namespace="projects")),
    path("", dashboard, name="home"),
]
