import datetime as dt

import pytest

from apps.projects.models import BoardApproval


@pytest.mark.django_db
def test_create_board_approval(project):
    a = BoardApproval.objects.create(
        project=project,
        motion_text="Approve sprinkler upgrade for $40,000.",
        vote_date=dt.date(2026, 4, 15),
        votes_for=4, votes_against=0, votes_abstain=1,
        minutes_reference="Apr 2026 minutes, p. 3",
    )
    assert a.votes_for == 4


@pytest.mark.django_db
def test_one_to_one_per_project(project):
    BoardApproval.objects.create(
        project=project,
        motion_text="First motion",
        vote_date=dt.date(2026, 4, 15),
        votes_for=4, votes_against=0, votes_abstain=0,
    )
    with pytest.raises(Exception):  # noqa: B017
        BoardApproval.objects.create(
            project=project,
            motion_text="Second motion",
            vote_date=dt.date(2026, 5, 15),
            votes_for=3, votes_against=1, votes_abstain=0,
        )
