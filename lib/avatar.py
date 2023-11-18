from models.user_avatar_type import UserAvatarType


class Avatar:
    @staticmethod
    def get_url(avatar_type: UserAvatarType, avatar_id: str | None) -> str:
        """
        Get the url of the avatar image.
        """

        if avatar_type == UserAvatarType.default:
            return 'TODO'  # TODO: default avatar image
        elif avatar_type == UserAvatarType.gravatar:
            return 'TODO'  # TODO: gravatar
        elif avatar_type == UserAvatarType.custom:
            return 'TODO'
        else:
            raise NotImplementedError(f'Unsupported avatar type: {avatar_type!r}')
