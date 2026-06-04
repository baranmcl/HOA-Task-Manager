from django.contrib import admin
from django.urls import include, path

from apps.projects.views.dashboard import dashboard
from apps.projects.views.help import help_page

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("roster/", include("apps.roster.urls", namespace="roster")),
    path("projects/", include("apps.projects.urls", namespace="projects")),
    path("help/", help_page, name="help"),
    path("", dashboard, name="home"),
]
