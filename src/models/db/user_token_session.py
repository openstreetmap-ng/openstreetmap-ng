from src.models.db.user_token import UserToken


class UserTokenSession(UserToken):
    __tablename__ = 'user_token_session'
