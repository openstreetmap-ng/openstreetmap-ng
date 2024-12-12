from app.limits import USER_TOKEN_ACCOUNT_CONFIRM_EXPIRE
from app.models.db.user_token import UserToken


class UserTokenAccountConfirm(UserToken):
    __tablename__ = 'user_token_account_confirm'
    __expire__ = USER_TOKEN_ACCOUNT_CONFIRM_EXPIRE
