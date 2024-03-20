from collections.abc import Sequence

import cython
from anyio import create_task_group
from shapely import Point, get_coordinates

from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import get_xattr
from app.models.db.user import User
from app.models.db.user_pref import UserPref
from app.models.validating.user_pref import UserPrefValidating
from app.repositories.changeset_repository import ChangesetRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.trace_repository import TraceRepository
from app.repositories.user_block_repository import UserBlockRepository


class User06Mixin:
    @staticmethod
    async def encode_user(user: User) -> dict:
        """
        >>> encode_user(User(...))
        {'user': {'@id': 1234, '@display_name': 'userName', ...}}
        """

        return {'user': await _encode_user(user, is_json=format_is_json())}

    @staticmethod
    async def encode_users(users: Sequence[User]) -> dict:
        """
        >>> encode_users([
        ...     User(...),
        ...     User(...),
        ... ])
        {'user': [{'@id': 1234, '@display_name': 'userName', ...}]}
        """

        is_json = format_is_json()
        encoded_users = [None] * len(users)

        async def task(i: int, user: User):
            encoded_users[i] = await _encode_user(user, is_json=is_json)

        async with create_task_group() as tg:
            for i, user in enumerate(users):
                tg.start_soon(task, i, user)

        if is_json:
            return {'users': encoded_users}
        else:
            return {'user': encoded_users}

    @staticmethod
    def encode_user_preferences(prefs: Sequence[UserPref]) -> dict:
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
    def decode_user_preferences(prefs: Sequence[dict[str, str]]) -> Sequence[UserPref]:
        """
        >>> decode_user_preferences([{'@k': 'key', '@v': 'value'}])
        [UserPref(key='key', value='value')]
        """

        user_id = auth_user().id
        seen_keys: set[str] = set()

        # check for duplicate keys
        for pref in prefs:
            key: str = pref['@k']
            if key in seen_keys:
                raise_for().pref_duplicate_key(key)
            seen_keys.add(key)

        return tuple(
            UserPref(
                **UserPrefValidating(
                    user_id=user_id,
                    app_id=None,  # 0.6 api does not support prefs partitioning
                    key=pref['@k'],
                    value=pref['@v'],
                ).to_orm_dict()
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

    changesets_count = None
    traces_count = None
    block_received_count = None
    block_received_active_count = None
    block_issued_count = None
    block_issued_active_count = None
    messages_received_count = None
    messages_received_unread_count = None
    messages_sent_count = None

    async def changesets_count_task() -> None:
        nonlocal changesets_count
        changesets_count = await ChangesetRepository.count_by_user_id(user.id)

    async def traces_count_task() -> None:
        nonlocal traces_count
        traces_count = await TraceRepository.count_by_user_id(user.id)

    async def block_received_count_task() -> None:
        nonlocal block_received_count, block_received_active_count
        total, active = await UserBlockRepository.count_received_by_user_id(user.id)
        block_received_count = total
        block_received_active_count = active

    async def block_issued_count_task() -> None:
        nonlocal block_issued_count, block_issued_active_count
        total, active = await UserBlockRepository.count_given_by_user_id(user.id)
        block_issued_count = total
        block_issued_active_count = active

    async def messages_received_count_task() -> None:
        nonlocal messages_received_count, messages_received_unread_count
        total, unread = await MessageRepository.count_received_by_user_id(user.id)
        messages_received_count = total
        messages_received_unread_count = unread

    async def messages_sent_count_task() -> None:
        nonlocal messages_sent_count
        messages_sent_count = await MessageRepository.count_sent_by_user_id(user.id)

    async with create_task_group() as tg:
        tg.start_soon(changesets_count_task)
        tg.start_soon(traces_count_task)
        tg.start_soon(block_received_count_task)
        tg.start_soon(block_issued_count_task)

        if access_private:
            tg.start_soon(messages_received_count_task)
            tg.start_soon(messages_sent_count_task)

    return {
        xattr('id'): user.id,
        xattr('display_name'): user.display_name,
        xattr('account_created'): user.created_at,
        'description': user.description,
        ('contributor_terms' if is_json else 'contributor-terms'): {
            xattr('agreed'): True,
            **({xattr('pd'): False} if access_private else {}),
        },
        'img': {xattr('href'): user.avatar_url},
        'roles': tuple(role.value for role in user.roles),
        'changesets': {xattr('count'): changesets_count},
        'traces': {xattr('count'): traces_count},
        'blocks': {
            'received': {
                xattr('count'): block_received_count,
                xattr('active'): block_received_active_count,
            },
            'issued': {
                xattr('count'): block_issued_count,
                xattr('active'): block_issued_active_count,
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
                'languages': _encode_languages(user.language, is_json=is_json),
                'messages': {
                    'received': {
                        xattr('count'): messages_received_count,
                        xattr('unread'): messages_received_unread_count,
                    },
                    'sent': {xattr('count'): messages_sent_count},
                },
            }
            if access_private
            else {}
        ),
    }


@cython.cfunc
def _encode_languages(language: str, *, is_json: cython.char):
    """
    >>> _encode_languages(['en', 'pl'])
    {'lang': ('en', 'pl')}
    """

    if is_json:
        return (language,)
    else:
        return {'lang': (language,)}


@cython.cfunc
def _encode_point(point: Point, *, is_json: cython.char) -> dict:
    """
    >>> _encode_point(Point(1, 2), is_json=False)
    {'@lon': 1, '@lat': 2}
    """

    x, y = get_coordinates(point)[0].tolist()

    if is_json:
        return {
            'lon': x,
            'lat': y,
        }
    else:
        return {
            '@lon': x,
            '@lat': y,
        }
