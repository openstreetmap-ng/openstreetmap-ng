from app.models.db.user_token import UserToken


class UserTokenResetPassword(UserToken):
    __tablename__ = 'user_token_reset_password'
