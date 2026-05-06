from django.http import Http404
from django.urls import path


def _stub(request):
    raise Http404


app_name = "accounts"
urlpatterns = [
    # Stub so LOGIN_URL = "accounts:login" resolves before Task 7 adds the real view.
    path("login/", _stub, name="login"),
]
