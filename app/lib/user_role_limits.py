from collections.abc import Collection

from app.models.db.user import UserRole


class UserRoleLimits:
    @staticmethod
    def get_changeset_max_size(roles: Collection[UserRole]) -> int:
        """
        Get the maximum size of a changeset for the given roles.

        >>> UserRoleLimits.get_changeset_max_size(())
        10_000
        """
        result = _CHANGESET_MAX_SIZE[None]
        for role in roles:
            value = _CHANGESET_MAX_SIZE.get(role)
            if value is not None and result < value:
                result = value
        return result

    @staticmethod
    def get_rate_limit_quota(roles: Collection[UserRole]) -> int:
        """
        Get the rate limit quota for the given roles.

        >>> UserRoleLimits.get_rate_limit_quota(())
        10_000
        """
        result = _RATE_LIMIT_QUOTA[None]
        for role in roles:
            value = _RATE_LIMIT_QUOTA.get(role)
            if value is not None and result < value:
                result = value
        return result


_CHANGESET_MAX_SIZE: dict[UserRole | None, int] = {
    None: 10_000,
    'moderator': 20_000,
    'administrator': 20_000,
}


_RATE_LIMIT_QUOTA: dict[UserRole | None, int] = {
    None: 10_000,
    'moderator': 25_000,
    'administrator': 25_000,
}
