from enum import Enum


class UserRole(str, Enum):
    moderator = 'moderator'
    administrator = 'administrator'

    @staticmethod
    def get_changeset_max_size(roles: tuple['UserRole', ...]) -> int:
        """
        Get the maximum size of a changeset for the given roles.

        >>> UserRole.get_changeset_max_size([])
        10_000
        """
        if not roles:
            return _changeset_max_size[None]
        return max(_changeset_max_size[r] for r in roles)

    @staticmethod
    def get_rate_limit_quota(roles: tuple['UserRole', ...]) -> int:
        """
        Get the rate limit quota for the given roles.

        >>> UserRole.get_rate_limit_quota([])
        10_000
        """
        if not roles:
            return _rate_limit_quota[None]
        return max(_rate_limit_quota[r] for r in roles)


_changeset_max_size = {
    None: 10_000,
    UserRole.moderator: 20_000,
    UserRole.administrator: 20_000,
}


_rate_limit_quota = {
    None: 10_000,
    UserRole.moderator: 25_000,
    UserRole.administrator: 25_000,
}
