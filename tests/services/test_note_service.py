import asyncio
from typing import cast

import pytest

from app.models.types import NoteId
from app.services import note_service
from app.services.note_service import NoteCommentSideEffect, NoteService


async def test_comment_rejects_deferred_side_effects_without_connection():
    with pytest.raises(ValueError, match='connection is required'):
        await NoteService.comment(
            NoteId(1),
            '',
            'closed',
            deferred_side_effects=[],
        )


async def test_run_comment_side_effects_best_effort(
    monkeypatch: pytest.MonkeyPatch,
):
    completed_emails: list[int] = []
    completed_subscriptions: list[int] = []

    async def send_activity_email(note, _comment):
        if note['id'] == 1:
            await asyncio.sleep(0)
            raise RuntimeError('injected delivery failure')
        await asyncio.sleep(0.01)
        completed_emails.append(note['id'])

    async def subscribe(_type, note_id):
        await asyncio.sleep(0.01)
        completed_subscriptions.append(note_id)

    monkeypatch.setattr(note_service, '_send_activity_email', send_activity_email)
    monkeypatch.setattr(
        note_service.UserSubscriptionService,
        'subscribe',
        staticmethod(subscribe),
    )

    def side_effect(note_id: int):
        return cast(
            NoteCommentSideEffect,
            (
                {
                    'id': 1,
                    'email': 'user@example.com',
                    'display_name': 'user',
                    'timezone': None,
                },
                frozenset({'web_user'}),
                {'id': note_id},
                {},
                True,
            ),
        )

    await NoteService.run_comment_side_effects(
        [side_effect(1), side_effect(2)],
        best_effort=True,
    )

    assert completed_emails == [2]
    assert sorted(completed_subscriptions) == [1, 2]
