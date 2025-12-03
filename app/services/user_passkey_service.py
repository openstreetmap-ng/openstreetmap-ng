from uuid import UUID

import cbor2
from starlette import status
from starlette.exceptions import HTTPException

from app.config import PASSKEY_LIMIT
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.lib.webauthn import (
    AAGUID_DB,
    parse_auth_data,
    parse_client_data,
    verify_assertion,
)
from app.models.proto.shared_pb2 import (
    LoginResponse,
    PasskeyAssertion,
    PasskeyCredential,
    PasskeyRegistration,
)
from app.models.types import Password, UserId
from app.queries.user_passkey_query import UserPasskeyQuery
from app.services.audit_service import audit
from app.services.user_passkey_challenge_service import UserPasskeyChallengeService
from app.services.user_password_service import UserPasswordService


class UserPasskeyService:
    @staticmethod
    async def register_passkey(registration: PasskeyRegistration) -> None:
        """Register a new passkey for the current user."""
        user_id = auth_user(required=True)['id']

        # Parse and validate client data
        client_data = parse_client_data(
            registration.client_data_json, expected_type='webauthn.create'
        )
        if await UserPasskeyChallengeService.pop(client_data['challenge']) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid challenge')

        # Parse and validate auth data
        auth_data_bytes = cbor2.loads(registration.attestation_object)['authData']
        auth_data = parse_auth_data(auth_data_bytes)
        if auth_data is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Missing credential data')

        transports = list(set(registration.transports))
        assert len(transports) <= 10
        assert all(len(tp) <= 20 for tp in transports)

        async with db(True) as conn:
            result = await conn.execute(
                """
                WITH passkey_count AS (
                    SELECT
                        -- Prevent count race conditions
                        pg_advisory_xact_lock(6205915937564190191::bigint # %(user_id)s),
                        COUNT(*) as cnt
                    FROM user_passkey
                    WHERE user_id = %(user_id)s
                )
                INSERT INTO user_passkey (
                    user_id, aaguid, credential_id,
                    algorithm, public_key, transports
                )
                SELECT
                    %(user_id)s, %(aaguid)s, %(credential_id)s,
                    %(algorithm)s, %(public_key)s, %(transports)s
                FROM passkey_count
                WHERE passkey_count.cnt < %(limit)s
                """,
                {
                    'user_id': user_id,
                    'aaguid': auth_data.aaguid,
                    'credential_id': auth_data.credential_id,
                    'algorithm': auth_data.algorithm,
                    'public_key': auth_data.public_key,
                    'transports': transports,
                    'limit': PASSKEY_LIMIT,
                },
            )
            if not result.rowcount:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, 'Passkey limit exceeded'
                )

            extra = {}
            aaguid_info = AAGUID_DB.get(auth_data.aaguid)
            if aaguid_info is not None:
                extra['aaguid_name'] = aaguid_info['name']
            await audit('add_passkey', conn, extra=extra)

    @staticmethod
    async def verify_passkey(
        assertion: PasskeyAssertion, *, require_uv: bool = True
    ) -> UserId | LoginResponse | None:
        """Verify a passkey assertion."""
        # Parse and validate client data
        client_data = parse_client_data(
            assertion.client_data_json, expected_type='webauthn.get'
        )
        if await UserPasskeyChallengeService.pop(client_data['challenge']) is None:
            return None

        # Parse and validate auth data
        parse_auth_data(assertion.authenticator_data, require_uv=require_uv)

        async with db(True) as conn:
            passkey = await UserPasskeyQuery.find_one_by_credential_id(
                assertion.credential_id, conn=conn
            )
            if passkey is None:
                StandardFeedback.raise_error(
                    None, t('two_fa.this_passkey_is_not_assigned_to_any_account')
                )

            # Verify assertion
            new_sign_count = verify_assertion(passkey, assertion)

            # Update sign count
            await conn.execute(
                """
                UPDATE user_passkey SET
                    sign_count = %s,
                    last_used_at = DEFAULT
                WHERE credential_id = %s
                """,
                (new_sign_count, passkey['credential_id']),
            )

            return passkey['user_id']

    @staticmethod
    async def remove_passkey(
        credential_id: bytes,
        *,
        password: Password | None,
        user_id: UserId | None = None,
    ) -> None:
        """Remove a passkey from a user's account."""
        if password is None:
            assert user_id is not None
        else:
            assert user_id is None
            user = auth_user(required=True)
            user_id = user['id']

            await UserPasswordService.verify_password(
                user,
                password,
                field_name='password',
                error_message=lambda: t('validation.password_is_incorrect'),
            )

        async with (
            db(True) as conn,
            await conn.execute(
                """
                DELETE FROM user_passkey
                WHERE credential_id = %s AND user_id = %s
                RETURNING aaguid
                """,
                (credential_id, user_id),
            ) as r,
        ):
            row: tuple[UUID] | None = await r.fetchone()
            if row is None:
                return

            extra = {}
            aaguid_info = AAGUID_DB.get(row[0])
            if aaguid_info is not None:
                extra['aaguid_name'] = aaguid_info['name']
            await audit(
                'remove_passkey',
                conn,
                target_user_id=(user_id if password is None else None),
                extra=extra,
            )

    @staticmethod
    async def rename_passkey(credential_id: bytes, *, name: str) -> str | None:
        """
        Rename a passkey for the current user.
        Empty name restores the default.
        Returns the effective display name or None if not found.
        """
        user_id = auth_user(required=True)['id']
        name_value = name.strip() or None

        async with (
            db(True) as conn,
            await conn.execute(
                """
                UPDATE user_passkey
                SET name = %s
                WHERE credential_id = %s
                  AND user_id = %s
                RETURNING name, aaguid
                """,
                (name_value, credential_id, user_id),
            ) as r,
        ):
            row: tuple[str | None, UUID] | None = await r.fetchone()
            if row is None:
                return None

        stored_name, aaguid = row
        if stored_name is not None:
            return stored_name

        aaguid_info = AAGUID_DB.get(aaguid)
        return aaguid_info['name'] if aaguid_info else t('two_fa.my_passkey')

    @staticmethod
    async def get_credentials(user_id: UserId) -> list[PasskeyCredential]:
        """Get credentials for a user's passkeys."""
        passkeys = await UserPasskeyQuery.find_all_by_user_id(user_id)
        return [
            PasskeyCredential(
                credential_id=p['credential_id'], transports=p['transports']
            )
            for p in passkeys
        ]
