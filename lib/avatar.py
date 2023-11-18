from typing import Any

from models.user_avatar_type import UserAvatarType


class Avatar:
    @staticmethod
    def get_url(avatar_type: UserAvatarType, avatar_id: Any) -> str:
        """
        Get the url of the avatar image.
        """

        if avatar_type == UserAvatarType.default:
            return '/static/img/avatar.webp'
        elif avatar_type == UserAvatarType.gravatar:
            return f'/api/web/avatar/gravatar/{avatar_id}'
        elif avatar_type == UserAvatarType.custom:
            return f'/api/web/avatar/custom/{avatar_id}'
        else:
            raise NotImplementedError(f'Unsupported avatar type: {avatar_type!r}')
