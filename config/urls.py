from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import include, path


@login_required
def home(request):
    return render(request, "home.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    # path("accounts/", include("apps.accounts.urls", namespace="accounts")),  # TODO uncomment in Task 3
    # path("roster/", include("apps.roster.urls", namespace="roster")),  # TODO uncomment in Task 3
    path("", home, name="home"),
]
