from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL

from app.db import db
from app.lib.translation import t
from app.lib.webauthn import AAGUID_DB
from app.models.db.user_passkey import UserPasskey
from app.models.types import UserId


class UserPasskeyQuery:
    @staticmethod
    async def check_any_by_user_id(user_id: UserId) -> bool:
        """Check if a user has any passkeys configured."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM user_passkey
                    WHERE user_id = %s
                )
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find_all_by_user_id(
        user_id: UserId, *, resolve_aaguid_db: bool = True
    ) -> list[UserPasskey]:
        """Find all passkeys for a user, ordered by creation date."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT *
                FROM user_passkey
                WHERE user_id = %s
                ORDER BY created_at
                """,
                (user_id,),
            ) as r,
        ):
            passkeys: list[UserPasskey] = await r.fetchall()  # type: ignore

        if resolve_aaguid_db:
            default_name = t('two_fa.my_passkey')
            for passkey in passkeys:
                passkey['aaguid_info'] = aaguid_info = AAGUID_DB.get(passkey['aaguid'])
                if passkey['name'] is not None:
                    pass
                elif aaguid_info is not None:
                    passkey['name'] = aaguid_info['name']
                else:
                    passkey['name'] = default_name

        return passkeys

    @staticmethod
    async def find_one_by_credential_id(
        credential_id: bytes,
        *,
        conn: AsyncConnection | None = None,
    ) -> UserPasskey | None:
        """Find a passkey by credential id, for update."""
        async with (
            db(conn) as conn,
            await conn.cursor(row_factory=dict_row).execute(
                SQL("""
                    SELECT * FROM user_passkey
                    WHERE credential_id = %s
                    {}
                """).format(SQL('FOR UPDATE' if not conn.read_only else '')),
                (credential_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore
