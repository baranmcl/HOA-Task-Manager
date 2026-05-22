import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import BoardApproval


@pytest.mark.django_db
def test_add_approval(auth_client, project):
    response = auth_client.post(
        reverse("projects:approval_add", args=[project.pk]),
        {
            "motion_text": "Approve $40k for sprinklers.",
            "vote_date": "2026-04-15",
            "votes_for": 4, "votes_against": 0, "votes_abstain": 1,
            "minutes_reference": "Apr 2026, p. 3",
        },
    )
    assert response.status_code == 302
    assert BoardApproval.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_edit_approval(auth_client, project):
    BoardApproval.objects.create(
        project=project, motion_text="Old", vote_date=dt.date(2026, 4, 15),
        votes_for=3, votes_against=2, votes_abstain=0,
    )
    response = auth_client.post(
        reverse("projects:approval_edit", args=[project.pk]),
        {
            "motion_text": "New motion",
            "vote_date": "2026-05-15",
            "votes_for": 5, "votes_against": 0, "votes_abstain": 0,
        },
    )
    assert response.status_code == 302
    project.board_approval.refresh_from_db()
    assert project.board_approval.motion_text == "New motion"
