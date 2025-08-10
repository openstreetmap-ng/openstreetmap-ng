from contextlib import nullcontext

import pytest

from app.models.db.report import ReportType, ReportTypeId
from app.models.db.report_comment import ReportAction, ReportActionId
from app.services.report_service import _validate_integrity


@pytest.mark.parametrize(
    ('type', 'type_id', 'action', 'action_id', 'should_pass'),
    [
        # Valid cases - actions that don't require action_id
        ('user', 1, 'user_profile', None, True),
        ('user', 1, 'user_account', None, True),
        ('anonymous_note', 1, 'generic', None, True),
        # Invalid cases - bad type
        ('invalid_type', 1, 'generic', None, False),
        ('note', 1, 'generic', None, False),
        # Invalid cases - bad action
        ('user', 1, 'generic', None, False),
        (
            'anonymous_note',
            1,
            'user_profile',
            None,
            False,
        ),
        # Invalid cases - action_id provided when it shouldn't be
        ('user', 1, 'user_profile', 123, False),
        ('user', 1, 'user_account', 123, False),
        ('anonymous_note', 1, 'generic', 123, False),
    ],
)
async def test_validate_integrity(
    type: ReportType,
    type_id: ReportTypeId,
    action: ReportAction,
    action_id: ReportActionId,
    should_pass: bool,
):
    with (
        nullcontext()
        if should_pass
        else pytest.raises((AssertionError, NotImplementedError))
    ):
        await _validate_integrity(type, type_id, action, action_id)
