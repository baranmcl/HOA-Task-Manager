import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods

from .forms import InviteUserForm, ProfileForm
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


@login_required
@user_passes_test(lambda u: u.is_staff)
def invite_user(request):
    """Create a new user with no usable password and email them an
    activation link. Staff-only because invite power = account creation
    power; we tighten the trust circle until 2FA lands.

    The activation link is the same /reset/<uidb64>/<token>/ URL the
    password-reset flow uses — Django's PasswordResetConfirmView accepts
    tokens for users with unusable passwords just as well as for users
    who have one. Reusing it means no new password-set view to maintain.
    """
    if request.method != "POST":
        return render(request, "accounts/invite_form.html", {"form": InviteUserForm()})

    form = InviteUserForm(request.POST)
    if not form.is_valid():
        return render(request, "accounts/invite_form.html", {"form": form})

    User = get_user_model()
    cleaned = form.cleaned_data
    new_user = User.objects.create(
        username=cleaned["email"],
        email=cleaned["email"],
        first_name=cleaned.get("first_name", "") or "",
        last_name=cleaned.get("last_name", "") or "",
        is_active=True,
    )
    new_user.set_unusable_password()
    new_user.save()

    if cleaned.get("roster_person"):
        new_user.profile.roster_person = cleaned["roster_person"]
        new_user.profile.save()

    # Build the activation link using the same machinery as password reset.
    uidb64 = urlsafe_base64_encode(force_bytes(new_user.pk))
    token = default_token_generator.make_token(new_user)
    activation_path = reverse(
        "accounts:password_reset_confirm",
        kwargs={"uidb64": uidb64, "token": token},
    )
    activation_url = request.build_absolute_uri(activation_path)

    context = {
        "invitee": new_user,
        "inviter": request.user,
        "inviter_name": request.user.profile.display_name,
        "activation_url": activation_url,
        "site_url": request.build_absolute_uri("/"),
    }
    subject = render_to_string("accounts/invite_subject.txt", context).strip()
    body = render_to_string("accounts/invite_email.txt", context)

    msg = EmailMultiAlternatives(
        subject=subject, body=body,
        from_email=None,  # falls back to DEFAULT_FROM_EMAIL
        to=[new_user.email],
    )
    msg.send(fail_silently=False)

    messages.success(
        request,
        f"Invitation sent to {new_user.email}. The link expires in 3 days.",
    )
    return redirect("accounts:invite_sent")


@login_required
@user_passes_test(lambda u: u.is_staff)
def invite_sent(request):
    return render(request, "accounts/invite_sent.html")


def password_reset_confirm(request, uidb64, token):
    """Stateless password reset confirm view.

    Replaces Django's PasswordResetConfirmView, which uses a session-stash
    redirect step (/reset/<uid>/<token>/ → 302 → /reset/<uid>/set-password/)
    to keep the token out of HTTP Referer headers. That design fails in
    production when email-safety scanners (Gmail, Outlook, M365 Safe Links)
    follow the redirect server-side before the user's actual click — the
    token ends up stashed in the scanner's session, and the user's
    subsequent click hits a session-less /set-password/ URL with
    validlink=False.

    Our SECURE_REFERRER_POLICY='same-origin' already prevents the
    Referer-leak risk that motivated session-stashing in upstream Django,
    so a stateless flow is both safer (works for real users) and no less
    secure (token still isn't leaked off-origin).

    This view validates the token from the URL on every request and either
    renders the form or the invalid-link page directly — no redirect, no
    session writes. Token consumption happens only on a successful POST
    (changing the password invalidates the token because user.password is
    part of the token generator's input).
    """
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    validlink = (
        user is not None
        and default_token_generator.check_token(user, token)
    )

    if not validlink:
        return render(request, "registration/password_reset_confirm.html", {
            "validlink": False,
        })

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            return redirect("accounts:password_reset_complete")
    else:
        form = SetPasswordForm(user)

    return render(request, "registration/password_reset_confirm.html", {
        "form": form,
        "validlink": True,
    })
