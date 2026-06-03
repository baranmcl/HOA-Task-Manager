from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(
        template_name="registration/login.html",
        redirect_authenticated_user=True,
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("backup/run/", views.backup_run_now, name="backup_run_now"),
    path("password/change/", auth_views.PasswordChangeView.as_view(
        success_url=reverse_lazy("accounts:password_change_done"),
    ), name="password_change"),
    path("password/change/done/", auth_views.PasswordChangeDoneView.as_view(),
         name="password_change_done"),

    # --- Password reset flow (Django built-ins, customized templates) ---
    # PasswordResetView intentionally shows the "sent" page whether or not
    # the email matches a real user, to prevent enumeration. Invite links
    # reuse this same machinery — see views.invite_user.
    path("password/reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    ), name="password_reset"),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password_reset_done"),
    # Custom stateless view replaces auth_views.PasswordResetConfirmView —
    # see the view's docstring for why. URL signature is unchanged so the
    # password-reset email template and Django's PasswordResetForm.save()
    # both continue to work without modification.
    path("reset/<uidb64>/<token>/", views.password_reset_confirm,
         name="password_reset_confirm"),
    path("reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password_reset_complete"),

    # --- Invite flow (custom; reuses Django's reset token URL) ---
    path("invite/", views.invite_user, name="invite_user"),
    path("invite/sent/", views.invite_sent, name="invite_sent"),
]
