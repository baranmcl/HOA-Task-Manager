import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ProfileForm
from .models import BackupLog

logger = logging.getLogger(__name__)


@login_required
def profile(request):
    profile_obj = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile_obj)
    return render(request, "accounts/profile.html", {
        "form": form,
        "profile": profile_obj,
        "latest_backup": BackupLog.objects.order_by("-run_date").first(),
    })


@login_required
@require_http_methods(["POST"])
def backup_run_now(request):
    """Trigger an on-demand database backup.

    Calls the same management command the middleware runs daily. Safe to
    invoke repeatedly — the command is idempotent on the day's BackupLog
    row and overwrites the R2 object at the same dated key. Exceptions
    from the command are caught here so the user always sees a flash
    message rather than a 500 page.
    """
    try:
        call_command("backup_database")
    except Exception:  # noqa: BLE001 - never surface a 500 from a click
        logger.exception("Manual backup failed")
        messages.error(request, "Backup failed — see server logs.")
        return redirect("accounts:profile")

    latest = BackupLog.objects.order_by("-run_date").first()
    if latest and latest.error:
        messages.warning(request, latest.error)
    else:
        messages.success(request, "Backup complete.")
    return redirect("accounts:profile")
