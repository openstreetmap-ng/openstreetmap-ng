from datetime import datetime, timedelta
from typing import Literal, NotRequired, TypedDict

from app.limits import (
    USER_TOKEN_ACCOUNT_CONFIRM_EXPIRE,
    USER_TOKEN_EMAIL_CHANGE_EXPIRE,
    USER_TOKEN_EMAIL_REPLY_EXPIRE,
    USER_TOKEN_RESET_PASSWORD_EXPIRE,
)
from app.models.db.mail import MailSource
from app.models.db.user import User
from app.models.types import Email, UserId, UserTokenId

UserTokenType = Literal['account_confirm', 'email_change', 'email_reply', 'reset_password']

USER_TOKEN_EXPIRE: dict[UserTokenType, timedelta] = {
    'account_confirm': USER_TOKEN_ACCOUNT_CONFIRM_EXPIRE,
    'email_change': USER_TOKEN_EMAIL_CHANGE_EXPIRE,
    'email_reply': USER_TOKEN_EMAIL_REPLY_EXPIRE,
    'reset_password': USER_TOKEN_RESET_PASSWORD_EXPIRE,
}


# TODO: validate from address
class UserTokenInit(TypedDict):
    id: UserTokenId
    type: UserTokenType
    user_id: UserId
    user_email_hashed: bytes  # TODO: email change expire all tokens
    token_hashed: bytes

    # runtime
    user: NotRequired[User]


class UserToken(UserTokenInit):
    created_at: datetime


class UserTokenEmailChangeInit(UserTokenInit):
    email_change_new: Email


class UserTokenEmailChange(UserTokenEmailChangeInit, UserToken):
    pass


class UserTokenEmailReplyInit(UserTokenInit):
    email_reply_source: MailSource
    email_reply_to_user_id: UserId
    email_reply_usage_count: int


class UserTokenEmailReply(UserTokenEmailReplyInit, UserToken):
    pass
