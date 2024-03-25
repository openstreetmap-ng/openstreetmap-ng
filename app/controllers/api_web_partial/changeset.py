from fastapi import APIRouter, Response
from pydantic import PositiveInt
from starlette import status

from app.lib.render_response import render_response
from app.lib.statement_context import joinedload_context
from app.lib.translation import t
from app.models.db.changeset_comment import ChangesetComment
from app.models.tag_style import TagStyleCollection
from app.repositories.changeset_comment_repository import ChangesetCommentRepository
from app.repositories.changeset_repository import ChangesetRepository
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/changeset')


@router.get('/{changeset_id:int}')
async def get_changeset(changeset_id: PositiveInt):
    changesets = await ChangesetRepository.find_many_by_query(changeset_ids=(changeset_id,), limit=1)

    if not changesets:
        return Response(None, status.HTTP_404_NOT_FOUND)
    with joinedload_context(ChangesetComment.user):
        await ChangesetCommentRepository.resolve_comments(changesets, limit_per_changeset=None, rich_text=True)

    changeset = changesets[0]
    tags_map = changeset.tags_styled_map
    comment_tag = tags_map.pop('comment', None)
    if comment_tag is None:
        comment_tag = TagStyleCollection('comment', t('browse.no_comment'))

    return render_response(
        'partial/changeset.jinja2',
        {
            'changeset': changeset,
            'tags': tags_map.values(),
            'comment_tag': comment_tag,
            'params': JSON_ENCODE(
                {
                    'id': changeset_id,
                    **({'bounds': changeset.bounds.bounds} if (changeset.bounds is not None) else {}),
                }
            ).decode(),
        },
    )
