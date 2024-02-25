from collections.abc import Sequence

import cython

from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import xattr
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment


class Changeset06Mixin:
    @staticmethod
    def encode_changeset(changeset: Changeset) -> dict:
        """
        >>> encode_changeset(Changeset(...))
        {'changeset': {'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}}
        """

        if format_is_json():
            return _encode_changeset(changeset, is_json=True)
        else:
            return {'changeset': _encode_changeset(changeset, is_json=False)}

    @staticmethod
    def encode_changesets(changesets: Sequence[Changeset]) -> dict:
        """
        >>> encode_changesets([
        ...     Changeset(...),
        ...     Changeset(...),
        ... ])
        {'changeset': [{'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}]}
        """

        if format_is_json():
            return {'changesets': tuple(_encode_changeset(changeset, is_json=True) for changeset in changesets)}
        else:
            return {'changeset': tuple(_encode_changeset(changeset, is_json=False) for changeset in changesets)}


@cython.cfunc
def _encode_changeset_comment(comment: ChangesetComment) -> dict:
    """
    >>> _encode_changeset_comment(ChangesetComment(...))
    {'@uid': 1, '@user': ..., '@date': ..., 'text': 'lorem ipsum'}
    """

    xattr_ = xattr  # read property once for performance

    return {
        xattr_('id'): comment.id,
        xattr_('date'): comment.created_at,
        **(
            {
                xattr_('uid'): comment.user_id,
                xattr_('user'): comment.user.display_name,
            }
            if comment.user_id is not None
            else {}
        ),
        'text': comment.body,
    }


@cython.cfunc
def _encode_changeset(changeset: Changeset, *, is_json: cython.char) -> dict:
    """
    >>> _encode_changeset(Changeset(...))
    {'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}
    """

    xattr_ = xattr  # read property once for performance

    if changeset.bounds is not None:
        minx, miny, maxx, maxy = changeset.bounds.bounds
        bounds_dict = {
            xattr_('minlon', custom_xml='min_lon'): minx,
            xattr_('minlat', custom_xml='min_lat'): miny,
            xattr_('maxlon', custom_xml='max_lon'): maxx,
            xattr_('maxlat', custom_xml='max_lat'): maxy,
        }
    else:
        bounds_dict = {}

    # TODO: comments service
    comments = ()

    if is_json:
        return {
            'type': 'changeset',
            'id': changeset.id,
            'created_at': changeset.created_at,
            **({'closed_at': changeset.closed_at} if (changeset.closed_at is not None) else {}),
            'open': changeset.closed_at is None,
            **(
                {
                    'uid': changeset.user_id,
                    'user': changeset.user.display_name,
                }
                if changeset.user_id is not None
                else {}
            ),
            **bounds_dict,
            'comments_count': len(changeset.comments),
            'changes_count': changeset.size,
            'tags': changeset.tags,
            **(
                {'discussion': tuple(_encode_changeset_comment(comment) for comment in comments)}
                if comments  #
                else {}
            ),
        }
    else:
        return {
            '@id': changeset.id,
            '@created_at': changeset.created_at,
            **({'@closed_at': changeset.closed_at} if (changeset.closed_at is not None) else {}),
            '@open': changeset.closed_at is None,
            **(
                {
                    '@uid': changeset.user_id,
                    '@user': changeset.user.display_name,
                }
                if changeset.user_id is not None
                else {}
            ),
            **bounds_dict,
            '@comments_count': len(changeset.comments),
            '@changes_count': changeset.size,
            'tag': tuple({'@k': k, '@v': v} for k, v in changeset.tags.items()),
            **(
                {'discussion': {'comment': tuple(_encode_changeset_comment(comment) for comment in comments)}}
                if comments
                else {}
            ),
        }
