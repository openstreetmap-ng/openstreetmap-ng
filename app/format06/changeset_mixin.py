from collections.abc import Sequence

import cython

from app.format06.tag_mixin import Tag06Mixin
from app.lib.format_style_context import format_is_json
from app.lib.xmltodict import XAttr
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment


@cython.cfunc
def _encode_changeset_comment(comment: ChangesetComment) -> dict:
    """
    >>> _encode_changeset_comment(ChangesetComment(...))
    {'@uid': 1, '@user': ..., '@date': ..., 'text': 'lorem ipsum'}
    """

    return {
        XAttr('id'): comment.id,
        XAttr('date'): comment.created_at,
        XAttr('uid'): comment.user_id,
        XAttr('user'): comment.user.display_name,
        'text': comment.body,
    }


class Changeset06Mixin:
    @staticmethod
    def encode_changeset(changeset: Changeset) -> dict:
        """
        >>> encode_changeset(Changeset(...))
        {'changeset': {'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}}
        """

        if changeset.bounds:
            minx, miny, maxx, maxy = changeset.bounds.bounds
            bounds_dict = {
                XAttr('minlon', custom_xml='min_lon'): minx,
                XAttr('minlat', custom_xml='min_lat'): miny,
                XAttr('maxlon', custom_xml='max_lon'): maxx,
                XAttr('maxlat', custom_xml='max_lat'): maxy,
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
                **({'closed_at': changeset.closed_at} if changeset.closed_at else {}),
                'open': not changeset.closed_at,
                'uid': changeset.user_id,
                'user': changeset.user.display_name,
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
                    **({'@closed_at': changeset.closed_at} if changeset.closed_at else {}),
                    '@open': not changeset.closed_at,
                    '@uid': changeset.user_id,
                    '@user': changeset.user.display_name,
                    **bounds_dict,
                    '@comments_count': len(changeset.comments),
                    '@changes_count': changeset.size,
                    'tag': Tag06Mixin.encode_tags(changeset.tags),
                    **(
                        {
                            'discussion': {
                                'comment': tuple(_encode_changeset_comment(comment) for comment in comments),
                            }
                        }
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
                    Changeset06Mixin.encode_changeset(changeset)['changeset'] for changeset in changesets
                )
            }
