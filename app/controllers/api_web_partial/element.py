from collections.abc import Sequence

from anyio import create_task_group
from fastapi import APIRouter
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format07 import Format07
from app.lib.element_list_formatter import format_element_members_list, format_element_parents_list
from app.lib.feature_name import feature_name
from app.lib.render_response import render_response
from app.lib.statement_context import options_context
from app.lib.tags_format import tags_format
from app.lib.translation import t
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.element_list_entry import ElementMemberEntry
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.tag_format import TagFormatCollection
from app.repositories.element_repository import ElementRepository
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/element')


@router.get('/{type}/{id:int}')
async def get_element(type: ElementType, id: PositiveInt):
    with options_context(joinedload(Element.changeset)):
        ref = ElementRef(type, id)
        elements = await ElementRepository.get_many_latest_by_element_refs((ref,), limit=1)
        element = elements[0] if elements else None

    if element is None:
        return render_response(
            'partial/not_found.jinja2',
            {'type': type, 'id': id},
        )

    is_latest = False
    list_parents: Sequence[ElementMemberEntry] | None = None
    full_data: Sequence[Element] | None = None
    list_elements: Sequence[ElementMemberEntry] | None = None

    async def check_latest_task():
        nonlocal is_latest
        is_latest = await ElementRepository.is_latest(element.versioned_ref)

    async def parents_task():
        nonlocal list_parents
        parents = await ElementRepository.get_many_parents_by_element_refs((element.element_ref,), limit=None)
        list_parents = format_element_parents_list(element.element_ref, parents)

    async def data_task():
        nonlocal full_data, list_elements
        with options_context(joinedload(Element.changeset).load_only(Changeset.user_id)):
            members_element_refs = frozenset(member.element_ref for member in element.members)
            members_elements = await ElementRepository.get_many_latest_by_element_refs(
                members_element_refs,
                recurse_ways=True,
                limit=None,
            )
        direct_members = tuple(member for member in members_elements if member.element_ref in members_element_refs)
        full_data = (element, *members_elements)
        list_elements = format_element_members_list(element.members, direct_members)

    async with create_task_group() as tg:
        tg.start_soon(check_latest_task)
        tg.start_soon(parents_task)
        if element.members:
            tg.start_soon(data_task)
        else:
            full_data = (element,)
            list_elements = ()

    changeset_tags_ = element.changeset.tags
    if 'comment' in changeset_tags_:
        changeset_tags = tags_format(changeset_tags_)
        comment_tag = changeset_tags['comment']
    else:
        comment_tag = TagFormatCollection('comment', t('browse.no_comment'))

    prev_version = element.version - 1 if element.version > 1 else None
    next_version = element.version + 1 if not is_latest else None
    name = feature_name(element.tags)
    tags = tags_format(element.tags)

    return render_response(
        'partial/element.jinja2',
        {
            'element': element,
            'changeset': element.changeset,
            'prev_version': prev_version,
            'next_version': next_version,
            'name': name,
            'tags': tags.values(),
            'comment_tag': comment_tag,
            'elements_len': len(list_elements),
            'part_of_len': len(list_parents),
            'params': JSON_ENCODE(
                {
                    'type': type,
                    'id': id,
                    'fullData': Format07.encode_elements(full_data),
                    'lists': {
                        'partOf': list_parents,
                        'elements': list_elements,
                    },
                }
            ).decode(),
        },
    )
