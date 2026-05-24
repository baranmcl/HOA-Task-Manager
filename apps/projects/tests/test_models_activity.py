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


@pytest.mark.django_db
def test_value_change_status_uses_human_labels(project, user):
    log = ActivityLog.objects.create(
        project=project, actor=user, verb="changed status",
        before_value={"status": "not_started"},
        after_value={"status": "in_progress"},
    )
    assert log.value_change == "Not started → In progress"


@pytest.mark.django_db
def test_value_change_project_creation_shows_title(project, user):
    log = ActivityLog.objects.create(
        project=project, actor=user, verb="created project",
        after_value={"title": "Sprinkler upgrade"},
    )
    assert log.value_change == "Sprinkler upgrade"


@pytest.mark.django_db
def test_value_change_raci_add_shows_person_and_role(project, user):
    log = ActivityLog.objects.create(
        project=project, actor=user, verb="added RACI assignment",
        after_value={"person": "Mike Smith", "role": "responsible"},
    )
    assert log.value_change == "Mike Smith (Responsible)"


@pytest.mark.django_db
def test_value_change_raci_remove_uses_before_only(project, user):
    log = ActivityLog.objects.create(
        project=project, actor=user, verb="removed RACI assignment",
        before_value={"person": "Laurel Baran", "role": "consulted"},
    )
    assert log.value_change == "Laurel Baran (Consulted)"


@pytest.mark.django_db
def test_value_change_attachment_added_shows_filename(project, user):
    log = ActivityLog.objects.create(
        project=project, actor=user, verb="added attachment",
        after_value={"filename": "vendor-quote.pdf"},
    )
    assert log.value_change == "vendor-quote.pdf"


@pytest.mark.django_db
def test_value_change_falls_back_for_unknown_shape(project, user):
    """Unknown value dicts should render cleanly, not crash or repr-dump."""
    log = ActivityLog.objects.create(
        project=project, actor=user, verb="did something exotic",
        after_value={"foo": "bar", "baz": 42},
    )
    # Order-independent check — Python dicts preserve insertion order but
    # we don't want this test to depend on that detail.
    assert "foo: bar" in log.value_change
    assert "baz: 42" in log.value_change


@pytest.mark.django_db
def test_value_change_empty_when_no_values(project, user):
    log = ActivityLog.objects.create(
        project=project, actor=user, verb="created project",
    )
    assert log.value_change == ""
