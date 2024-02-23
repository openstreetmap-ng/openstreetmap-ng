from collections.abc import Sequence

import cython

from app.format06.tag_mixin import Tag06Mixin
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import xattr
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment


@cython.cfunc
def _encode_changeset_comment(comment: ChangesetComment) -> dict:
    """
    >>> _encode_changeset_comment(ChangesetComment(...))
    {'@uid': 1, '@user': ..., '@date': ..., 'text': 'lorem ipsum'}
    """

    return {
        xattr('id'): comment.id,
        xattr('date'): comment.created_at,
        **(
            {
                xattr('uid'): comment.user_id,
                xattr('user'): comment.user.display_name,
            }
            if comment.user_id is not None
            else {}
        ),
        'text': comment.body,
    }


class Changeset06Mixin:
    @staticmethod
    def encode_changeset(changeset: Changeset) -> dict:
        """
        >>> encode_changeset(Changeset(...))
        {'changeset': {'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}}
        """

        if changeset.bounds is not None:
            minx, miny, maxx, maxy = changeset.bounds.bounds
            bounds_dict = {
                xattr('minlon', custom_xml='min_lon'): minx,
                xattr('minlat', custom_xml='min_lat'): miny,
                xattr('maxlon', custom_xml='max_lon'): maxx,
                xattr('maxlat', custom_xml='max_lat'): maxy,
            }
        else:
            bounds_dict = {}

        # TODO: comments service
        comments = ()

        if format_is_json():
            return {
                'type': 'changeset',
                'id': changeset.id,
                'created_at': changeset.created_at,
                **({'closed_at': changeset.closed_at} if changeset.closed_at is not None else {}),
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
                    if comments
                    else {}
                ),
            }
        else:
            return {
                'changeset': {
                    '@id': changeset.id,
                    '@created_at': changeset.created_at,
                    **({'@closed_at': changeset.closed_at} if changeset.closed_at is not None else {}),
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
                    'tag': Tag06Mixin.encode_tags(changeset.tags),
                    **(
                        {'discussion': {'comment': tuple(_encode_changeset_comment(comment) for comment in comments)}}
                        if comments
                        else {}
                    ),
                }
            }

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
            return {'elements': tuple(Changeset06Mixin.encode_changeset(changeset) for changeset in changesets)}
        else:
            return {
                'changeset': tuple(
                    Changeset06Mixin.encode_changeset(changeset)['changeset']  #
                    for changeset in changesets
                )
            }
