from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path


@login_required
def home(request):
    return render(request, "home.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    # path("accounts/", include("apps.accounts.urls", namespace="accounts")),  # Task 3
    # path("roster/", include("apps.roster.urls", namespace="roster")),  # Task 3
    path("", home, name="home"),
]
