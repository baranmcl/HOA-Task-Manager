"""ActivityLog writers. The actor is provided per-request by views via set_actor()."""

import threading

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import (
    ActivityLog,
    BoardApproval,
    Project,
    RACIAssignment,
)
from .models.attachment import Attachment

_state = threading.local()


def set_actor(user) -> None:
    _state.actor = user


def _actor():
    return getattr(_state, "actor", None)


# --- Project ---

@receiver(pre_save, sender=Project)
def _project_capture_old(sender, instance, **kwargs):
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._old_status = old.status if old else None
    else:
        instance._old_status = None


@receiver(post_save, sender=Project)
def _project_log(sender, instance, created, **kwargs):
    actor = _actor()
    if actor is None:
        return
    if created:
        ActivityLog.objects.create(
            project=instance, actor=actor, verb="created project",
            after_value={"title": instance.title},
        )
        return
    old_status = getattr(instance, "_old_status", None)
    if old_status is not None and old_status != instance.status:
        ActivityLog.objects.create(
            project=instance, actor=actor, verb="changed status",
            before_value={"status": old_status},
            after_value={"status": instance.status},
        )


# --- RACI ---

@receiver(post_save, sender=RACIAssignment)
def _raci_added(sender, instance, created, **kwargs):
    if not created:
        return
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="added RACI assignment",
        after_value={"person": instance.person.name, "role": instance.role},
    )


@receiver(post_delete, sender=RACIAssignment)
def _raci_removed(sender, instance, **kwargs):
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="removed RACI assignment",
        before_value={"person": instance.person.name, "role": instance.role},
    )


# --- BoardApproval ---

@receiver(post_save, sender=BoardApproval)
def _approval_saved(sender, instance, created, **kwargs):
    actor = _actor()
    if actor is None:
        return
    verb = "added board approval" if created else "updated board approval"
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb=verb,
        after_value={"vote_date": str(instance.vote_date), "summary": instance.vote_summary},
    )


# --- Attachment ---

@receiver(post_save, sender=Attachment)
def _attachment_added(sender, instance, created, **kwargs):
    if not created:
        return
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="added attachment",
        after_value={"filename": instance.original_filename},
    )


@receiver(post_delete, sender=Attachment)
def _attachment_removed(sender, instance, **kwargs):
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="removed attachment",
        before_value={"filename": instance.original_filename},
    )
