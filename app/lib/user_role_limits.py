from functools import cache

from app.models.db.user import UserRole


class UserRoleLimits:
    @cache
    @staticmethod
    def get_changeset_max_size(roles: tuple[UserRole, ...]) -> int:
        """
        Get the maximum size of a changeset for the given roles.

        >>> UserRoleLimits.get_changeset_max_size([])
        10_000
        """
        if not roles:
            return _changeset_max_size[None]
        return max(_changeset_max_size[r] for r in roles)

    @cache
    @staticmethod
    def get_rate_limit_quota(roles: tuple[UserRole, ...]) -> int:
        """
        Get the rate limit quota for the given roles.

        >>> UserRoleLimits.get_rate_limit_quota([])
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
