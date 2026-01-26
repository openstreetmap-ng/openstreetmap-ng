from app.models.db.user import UserRole


class UserRoleLimits:
    @staticmethod
    def get_changeset_max_size(roles: list[UserRole] | None):
        """Get the maximum size of a changeset for the given roles."""
        result = _CHANGESET_MAX_SIZE[None]
        if roles is None:
            return result

        for role in roles:
            value = _CHANGESET_MAX_SIZE.get(role)
            if value is not None and result < value:
                result = value

        return result

    @staticmethod
    def get_rate_limit_quota(roles: list[UserRole] | None):
        """Get the rate limit quota for the given roles."""
        result = _RATE_LIMIT_QUOTA[None]
        if roles is None:
            return result

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
