from psycopg import AsyncConnection

from app.db import db_count, db_fetchall, db_fetchone
from app.lib.auth.webauthn import AAGUID_DB
from app.lib.text.translation import t
from app.models.db.user_passkey import UserPasskey
from app.models.types import UserId


class UserPasskeyQuery:
    @staticmethod
    async def check_any_by_user_id(user_id: UserId) -> bool:
        """Check if a user has any passkeys configured."""
        return await db_count('user_passkey', where={'user_id': user_id}) > 0

    @staticmethod
    async def find_all_by_user_id(user_id: UserId, *, resolve_aaguid_db: bool = True):
        """Find all passkeys for a user, ordered by creation date."""
        passkeys = await db_fetchall(
            UserPasskey,
            t"""
                SELECT * FROM user_passkey
                WHERE user_id = {user_id}
                ORDER BY created_at
            """,
        )

        if resolve_aaguid_db:
            default_name = t('two_fa.my_passkey')

            for passkey in passkeys:
                aaguid_info = AAGUID_DB.get(passkey['aaguid'])

                if passkey['name'] is not None:
                    pass
                elif aaguid_info is not None:
                    passkey['name'] = aaguid_info['name']
                else:
                    passkey['name'] = default_name

                if aaguid_info is not None:
                    icon_light = aaguid_info.get('icon_light')
                    icon_dark = aaguid_info.get('icon_dark')
                    if icon_light is not None and icon_dark is not None:
                        passkey['icons'] = (icon_light, icon_dark)
                    elif icon_light is not None:
                        passkey['icons'] = (icon_light, icon_light)
                    elif icon_dark is not None:
                        passkey['icons'] = (icon_dark, icon_dark)

        return passkeys

    @staticmethod
    async def find_one_by_credential_id(
        credential_id: bytes,
        *,
        conn: AsyncConnection | None = None,
    ) -> UserPasskey | None:
        """Find a passkey by credential id, for update."""
        return await db_fetchone(
            UserPasskey,
            t'SELECT * FROM user_passkey WHERE credential_id = {credential_id}',
            for_update=True,
            conn=conn,
        )
