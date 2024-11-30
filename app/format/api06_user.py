from asyncio import TaskGroup
from collections.abc import Collection, Iterable

import cython
import numpy as np
from shapely import Point, lib

from app.config import APP_URL
from app.lib.auth_context import auth_user
from app.lib.date_utils import legacy_date
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import get_xattr
from app.models.db.user import User
from app.models.db.user_pref import UserPref
from app.models.validating.user_pref import UserPrefValidating
from app.queries.changeset_query import ChangesetQuery
from app.queries.message_query import MessageQuery
from app.queries.trace_query import TraceQuery
from app.queries.user_block_query import UserBlockQuery


class User06Mixin:
    @staticmethod
    async def encode_user(user: User) -> dict:
        """
        >>> encode_user(User(...))
        {'user': {'@id': 1234, '@display_name': 'userName', ...}}
        """
        return {'user': await _encode_user(user, is_json=format_is_json())}

    @staticmethod
    async def encode_users(users: Iterable[User]) -> dict:
        """
        >>> encode_users([
        ...     User(...),
        ...     User(...),
        ... ])
        {'user': [{'@id': 1234, '@display_name': 'userName', ...}]}
        """
        is_json = format_is_json()
        async with TaskGroup() as tg:
            tasks = tuple(tg.create_task(_encode_user(user, is_json=is_json)) for user in users)
        encoded_users = tuple(task.result() for task in tasks)
        return {'users': encoded_users} if is_json else {'user': encoded_users}

    @staticmethod
    def encode_user_preferences(prefs: Iterable[UserPref]) -> dict:
        """
        >>> encode_user_preferences([
        ...     UserPref(key='key1', value='value1'),
        ...     UserPref(key='key2', value='value2'),
        ... ])
        {'preferences': {'preference': [{'@k': 'key1', '@v': 'value1'}, {'@k': 'key2', '@v': 'value2'}]}}
        """
        if format_is_json():
            return {'preferences': {pref.key: pref.value for pref in prefs}}
        else:
            return {'preferences': {'preference': tuple({'@k': pref.key, '@v': pref.value} for pref in prefs)}}

    @staticmethod
    def decode_user_preferences(prefs: Collection[dict[str, str]]) -> tuple[UserPref, ...]:
        """
        >>> decode_user_preferences([{'@k': 'key', '@v': 'value'}])
        [UserPref(key='key', value='value')]
        """
        # check for duplicate keys
        seen_keys: set[str] = set()
        for pref in prefs:
            key: str = pref['@k']
            if key in seen_keys:
                raise_for.pref_duplicate_key(key)
            seen_keys.add(key)

        user_id = auth_user(required=True).id
        return tuple(
            UserPref(
                **UserPrefValidating(
                    user_id=user_id,
                    app_id=None,  # 0.6 api does not support prefs partitioning
                    key=pref['@k'],
                    value=pref['@v'],
                ).__dict__
            )
            for pref in prefs
        )


async def _encode_user(user: User, *, is_json: cython.char) -> dict:
    """
    >>> _encode_user(User(...))
    {'@id': 1234, '@display_name': 'userName', ...}
    """
    current_user = auth_user()
    access_private: cython.char = (current_user is not None) and (current_user.id == user.id)
    xattr = get_xattr(is_json=is_json)

    async with TaskGroup() as tg:
        changesets_task = tg.create_task(ChangesetQuery.count_by_user_id(user.id))
        traces_task = tg.create_task(TraceQuery.count_by_user_id(user.id))
        block_received_task = tg.create_task(UserBlockQuery.count_received_by_user_id(user.id))
        block_issued_task = tg.create_task(UserBlockQuery.count_given_by_user_id(user.id))
        if access_private:
            messages_count_task = tg.create_task(MessageQuery.count_by_user_id(user.id))
        else:
            messages_count_task = None

    changesets_num = changesets_task.result()
    traces_num = traces_task.result()
    block_received_num, block_received_active_num = block_received_task.result()
    block_issued_num, block_issued_active_num = block_issued_task.result()
    if messages_count_task is not None:
        messages_received_num, messages_unread_num, messages_sent_num = messages_count_task.result()
    else:
        messages_received_num = messages_unread_num = messages_sent_num = 0

    return {
        xattr('id'): user.id,
        xattr('display_name'): user.display_name,
        xattr('account_created'): legacy_date(user.created_at),
        'description': user.description,
        ('contributor_terms' if is_json else 'contributor-terms'): {
            xattr('agreed'): True,
            **({xattr('pd'): False} if access_private else {}),
        },
        'img': {xattr('href'): f'{APP_URL}{user.avatar_url}'},
        'roles': tuple(role.value for role in user.roles),
        'changesets': {xattr('count'): changesets_num},
        'traces': {xattr('count'): traces_num},
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
        # private section
        **(
            {
                **(
                    {
                        'home': {
                            **_encode_point(user.home_point, is_json=is_json),
                            xattr('zoom'): 15,  # default home zoom level
                        }
                    }
                    if (user.home_point is not None)
                    else {}
                ),
                'languages': _encode_language(user.language, is_json=is_json),
                'messages': {
                    'received': {
                        xattr('count'): messages_received_num,
                        xattr('unread'): messages_unread_num,
                    },
                    'sent': {xattr('count'): messages_sent_num},
                },
            }
            if access_private
            else {}
        ),
    }


@cython.cfunc
def _encode_language(language: str, *, is_json: cython.char):
    """
    >>> _encode_language('en')
    {'lang': ('en',)}
    """
    return (language,) if is_json else {'lang': (language,)}


@cython.cfunc
def _encode_point(point: Point, *, is_json: cython.char) -> dict:
    """
    >>> _encode_point(Point(1, 2), is_json=False)
    {'@lon': 1, '@lat': 2}
    """
    x, y = lib.get_coordinates(np.asarray(point, dtype=np.object_), False, False)[0].tolist()
    return {'lon': x, 'lat': y} if is_json else {'@lon': x, '@lat': y}
