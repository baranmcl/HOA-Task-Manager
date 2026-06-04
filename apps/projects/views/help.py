"""In-app Help / Support page.

Static (or close to static) content; just a render-and-show view. Sectioned
content lives in the template rather than in the view to keep editing the
copy a non-code task.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def help_page(request):
    return render(request, "help.html")
