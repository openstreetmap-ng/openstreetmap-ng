from app.limits import USER_TOKEN_RESET_PASSWORD_EXPIRE
from app.models.db.user_token import UserToken


class UserTokenResetPassword(UserToken):
    __tablename__ = 'user_token_reset_password'
    __expire__ = USER_TOKEN_RESET_PASSWORD_EXPIRE
