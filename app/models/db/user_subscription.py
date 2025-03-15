from typing import Literal, TypedDict

from app.models.types import UserId, UserSubscriptionTargetId

UserSubscriptionTarget = Literal['changeset', 'diary', 'note', 'user']


class UserSubscription(TypedDict):
    user_id: UserId
    target: UserSubscriptionTarget
    target_id: UserSubscriptionTargetId
