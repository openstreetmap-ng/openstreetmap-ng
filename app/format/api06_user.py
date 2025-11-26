from asyncio import TaskGroup

import cython
from shapely import Point, get_coordinates

from app.config import APP_URL
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import get_xattr
from app.models.db.user import User, user_avatar_url
from app.models.db.user_pref import UserPref, UserPrefListValidator
from app.models.types import UserPrefKey
from app.queries.changeset_query import ChangesetQuery
from app.queries.message_query import MessageQuery
from app.queries.trace_query import TraceQuery
from app.queries.user_block_query import UserBlockQuery
from app.queries.user_profile_query import UserProfileQuery


class User06Mixin:
    @staticmethod
    async def encode_user(user: User) -> dict:
        """
        >>> encode_user(User(...))
        {'user': {'@id': 1234, '@display_name': 'userName', ...}}
        """
        return {'user': await _encode_user(user, is_json=format_is_json())}

    @staticmethod
    async def encode_users(users: list[User]) -> dict:
        """
        >>> encode_users([
        ...     User(...),
        ...     User(...),
        ... ])
        {'user': [{'@id': 1234, '@display_name': 'userName', ...}]}
        """
        is_json = format_is_json()

        async with TaskGroup() as tg:
            tasks = [
                tg.create_task(_encode_user(user, is_json=is_json)) for user in users
            ]

        return {('users' if is_json else 'user'): [task.result() for task in tasks]}

    @staticmethod
    def encode_user_preferences(prefs: list[UserPref]) -> dict:
        """
        >>> encode_user_preferences([
        ...     UserPref(key='key1', value='value1'),
        ...     UserPref(key='key2', value='value2'),
        ... ])
        {'preferences': {'preference': [{'@k': 'key1', '@v': 'value1'}, {'@k': 'key2', '@v': 'value2'}]}}
        """
        if format_is_json():
            return {'preferences': {pref['key']: pref['value'] for pref in prefs}}

        return {
            'preferences': {
                'preference': [
                    {'@k': pref['key'], '@v': pref['value']} for pref in prefs
                ]
            }
        }

    @staticmethod
    def decode_user_preferences(prefs: list[dict[str, str]] | None) -> list[UserPref]:
        """
        >>> decode_user_preferences([{'@k': 'key', '@v': 'value'}])
        [UserPref(key='key', value='value')]
        """
        if not prefs:
            return []

        # Check for duplicate keys
        seen_keys = set[UserPrefKey]()
        for pref in prefs:
            key: UserPrefKey = pref['@k']  # type: ignore
            if key in seen_keys:
                raise_for.pref_duplicate_key(key)
            seen_keys.add(key)

        user_id = auth_user(required=True)['id']
        user_prefs: list[UserPref] = [  # type: ignore
            {
                'user_id': user_id,
                'app_id': None,  # 0.6 api does not support prefs partitioning
                'key': pref['@k'],
                'value': pref['@v'],
            }
            for pref in prefs
        ]
        return UserPrefListValidator.validate_python(user_prefs)


async def _encode_user(user: User, *, is_json: cython.bint) -> dict:
    """
    >>> _encode_user(User(...))
    {'@id': 1234, '@display_name': 'userName', ...}
    """
    user_id = user['id']
    current_user = auth_user()
    access_private: cython.bint
    access_private = current_user is not None and current_user['id'] == user_id
    xattr = get_xattr(is_json=is_json)

    async with TaskGroup() as tg:
        user_profile_t = tg.create_task(
            UserProfileQuery.get_by_user_id(user_id, resolve_rich_text=False)
        )
        changesets_t = tg.create_task(ChangesetQuery.count_by_user(user_id))
        traces_t = tg.create_task(TraceQuery.count_by_user(user_id))
        block_received_t = tg.create_task(
            UserBlockQuery.count_received_by_user(user_id)
        )
        block_issued_t = tg.create_task(UserBlockQuery.count_given_by_user(user_id))
        messages_count_t = (
            tg.create_task(MessageQuery.count_by_user(user_id))
            if access_private
            else None
        )

    block_received_num, block_received_active_num = block_received_t.result()
    block_issued_num, block_issued_active_num = block_issued_t.result()

    if messages_count_t is not None:
        messages_received_num, messages_unread_num, messages_sent_num = (
            messages_count_t.result()
        )
    else:
        messages_received_num = messages_unread_num = messages_sent_num = 0

    contributor_terms_key = 'contributor_terms' if is_json else 'contributor-terms'

    # Build public user info
    result = {
        xattr('id'): user_id,
        xattr('display_name'): user['display_name'],
        xattr('account_created'): user['created_at'],
        'description': user_profile_t.result()['description'] or '',
        contributor_terms_key: {
            xattr('agreed'): True,
        },
        'img': {xattr('href'): f'{APP_URL}{user_avatar_url(user)}'},
        'roles': user['roles'],
        'changesets': {xattr('count'): changesets_t.result()},
        'traces': {xattr('count'): traces_t.result()},
        'blocks': {
            'received': {
                xattr('count'): block_received_num,
                xattr('active'): block_received_active_num,
            },
            'issued': {
                xattr('count'): block_issued_num,
                xattr('active'): block_issued_active_num,
            },
        },
    }
    if not access_private:
        return result

    # Set pd (public domain) indicator for backward compatibility
    result[contributor_terms_key][xattr('pd')] = False

    result['languages'] = _encode_language(user['language'], is_json=is_json)
    result['messages'] = {
        'received': {
            xattr('count'): messages_received_num,
            xattr('unread'): messages_unread_num,
        },
        'sent': {
            xattr('count'): messages_sent_num,
        },
    }

    # Set home location if available
    home_point = user['home_point']
    if home_point is not None:
        result['home'] = {
            **_encode_point(home_point, is_json=is_json),
            xattr('zoom'): 15,
        }

    return result


@cython.cfunc
def _encode_language(language: str, *, is_json: cython.bint):
    """
    >>> _encode_language('en')
    {'lang': ['en']}
    """
    return [language] if is_json else {'lang': [language]}


@cython.cfunc
def _encode_point(point: Point, *, is_json: cython.bint) -> dict:
    """
    >>> _encode_point(Point(1, 2), is_json=False)
    {'@lon': 1, '@lat': 2}
    """
    x, y = get_coordinates(point).round(7)[0].tolist()
    return {'lon': x, 'lat': y} if is_json else {'@lon': x, '@lat': y}
