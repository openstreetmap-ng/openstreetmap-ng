from fastapi import APIRouter, Response
from pydantic import PositiveInt
from starlette import status

from app.lib.render_response import render_response
from app.lib.statement_context import joinedload_context
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.tag_format import TagFormatCollection
from app.repositories.element_repository import ElementRepository
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/element')


@router.get('/{type}/{id:int}')
async def get_element(type: ElementType, id: PositiveInt):
    with joinedload_context(Element.changeset):
        ref = ElementRef(type, id)
        elements = await ElementRepository.get_many_latest_by_element_refs((ref,), limit=1)
        element = elements[0] if elements else None

    if element is None:
        return render_response(
            'partial/not_found.jinja2',
            {'type': type, 'id': id},
        )

    is_latest = True
    prev_version = element.version - 1 if element.version > 1 else None
    next_version = element.version + 1 if not is_latest else None

    changeset_tags_ = element.changeset.tags
    if 'comment' in changeset_tags_:
        changeset_tags = tags_format(changeset_tags_)
        comment_tag = changeset_tags['comment']
    else:
        comment_tag = TagFormatCollection('comment', t('browse.no_comment'))

    tags = tags_format(element.tags)

    return render_response(
        'partial/element.jinja2',
        {
            'element': element,
            'changeset': element.changeset,
            'prev_version': prev_version,
            'next_version': next_version,
            'tags': tags.values(),
            'comment_tag': comment_tag,
            'params': JSON_ENCODE(
                {
                    # **({'bounds': changeset.bounds.bounds} if (changeset.bounds is not None) else {}),
                    # TODO: part of data
                    # TODO: members data
                    #'members': members,
                }
            ).decode(),
        },
    )
