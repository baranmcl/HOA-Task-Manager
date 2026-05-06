from django.http import Http404
from django.urls import path


def _stub(request):
    raise Http404


app_name = "roster"
urlpatterns = [
    # Stub so sidebar roster:list reference resolves before the real view is added.
    path("", _stub, name="list"),
]
