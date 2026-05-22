import pytest

from apps.projects.models import ActivityLog


@pytest.mark.django_db
def test_create_activity_log(project, user):
    log = ActivityLog.objects.create(
        project=project,
        actor=user,
        verb="created project",
    )
    assert log.verb == "created project"
    assert log.before_value is None
    assert log.after_value is None


@pytest.mark.django_db
def test_activity_log_ordered_newest_first(project, user):
    ActivityLog.objects.create(project=project, actor=user, verb="a")
    b = ActivityLog.objects.create(project=project, actor=user, verb="b")
    logs = list(ActivityLog.objects.all())
    assert logs[0].pk == b.pk
