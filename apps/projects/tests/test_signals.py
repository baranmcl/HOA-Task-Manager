import pytest

from apps.projects.models import (
    ActivityLog,
    Project,
    ProjectStatus,
    RACIAssignment,
    RACIRole,
)
from apps.projects.signals import set_actor


@pytest.mark.django_db
def test_project_create_logs(user, category):
    set_actor(user)
    p = Project.objects.create(title="Y", category=category, created_by=user)
    logs = ActivityLog.objects.filter(project=p, verb="created project")
    assert logs.exists()


@pytest.mark.django_db
def test_status_change_logs_before_after(user, project):
    set_actor(user)
    project.status = ProjectStatus.IN_PROGRESS
    project.save()
    log = ActivityLog.objects.filter(project=project, verb="changed status").first()
    assert log is not None
    assert log.before_value == {"status": "not_started"}
    assert log.after_value == {"status": "in_progress"}


@pytest.mark.django_db
def test_raci_add_logs(user, project, person):
    set_actor(user)
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    log = ActivityLog.objects.filter(project=project, verb="added RACI assignment").first()
    assert log is not None
    assert log.after_value == {"person": person.name, "role": "responsible"}


@pytest.mark.django_db
def test_raci_remove_logs(user, project, person):
    set_actor(user)
    a = RACIAssignment.objects.create(project=project, person=person, role=RACIRole.CONSULTED)
    a.delete()
    log = ActivityLog.objects.filter(project=project, verb="removed RACI assignment").first()
    assert log is not None
