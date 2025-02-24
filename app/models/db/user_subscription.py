from typing import Literal, TypedDict

from app.models.db.changeset import ChangesetId
from app.models.db.diary import DiaryId
from app.models.db.note import NoteId
from app.models.db.user import UserId

UserSubscriptionTarget = Literal['changeset', 'diary', 'note', 'user']
UserSubscriptionTargetId = ChangesetId | DiaryId | NoteId | UserId


class UserSubscription(TypedDict):
    user_id: UserId
    target: UserSubscriptionTarget
    target_id: UserSubscriptionTargetId
