from django.http import Http404
from django.urls import path


def _stub(request):
    raise Http404


app_name = "accounts"
urlpatterns = [
    # Stubs so sidebar URL references resolve before Task 7 adds real views.
    path("login/", _stub, name="login"),
    path("logout/", _stub, name="logout"),
    path("profile/", _stub, name="profile"),
]
