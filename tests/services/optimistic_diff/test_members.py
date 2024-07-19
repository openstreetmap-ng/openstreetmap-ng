import pytest
from shapely import Point

from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element_ref import ElementRef
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff


async def test_members_simple(changeset_id: int):
    elements = (
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='way',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=None,
            members=[ElementMember(order=0, type='node', id=-1, role='')],
        ),
    )

    assigned_ref_map = await OptimisticDiff.run(elements)
    node_id = assigned_ref_map[ElementRef('node', -1)][0].id
    way_id = assigned_ref_map[ElementRef('way', -1)][0].id

    elements = await ElementQuery.get_by_refs((ElementRef('way', way_id),), limit=1)
    element = elements[0]
    await ElementMemberQuery.resolve_members(elements)

    assert element.members[0].type == 'node'
    assert element.members[0].id == node_id
    assert element.members[0].role == ''


async def test_members_delete(changeset_id: int):
    elements = (
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='way',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=None,
            members=[ElementMember(order=0, type='node', id=-1, role='')],
        ),
        Element(
            changeset_id=changeset_id,
            type='way',
            id=-1,
            version=2,
            visible=False,
            tags={},
            point=None,
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=2,
            visible=False,
            tags={},
            point=None,
            members=[],
        ),
    )

    assigned_ref_map = await OptimisticDiff.run(elements)
    assert len(assigned_ref_map[ElementRef('node', -1)]) == 2
    assert len(assigned_ref_map[ElementRef('way', -1)]) == 2


async def test_members_self_reference(changeset_id: int):
    elements = (
        Element(
            changeset_id=changeset_id,
            type='relation',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=None,
            members=[ElementMember(order=0, type='relation', id=-1, role='role')],
        ),
        Element(
            changeset_id=changeset_id,
            type='relation',
            id=-1,
            version=2,
            visible=False,
            tags={},
            point=None,
            members=[],
        ),
    )

    assigned_ref_map = await OptimisticDiff.run(elements)
    relation_id = assigned_ref_map[ElementRef('relation', -1)][0].id

    elements = await ElementQuery.get_by_refs((ElementRef('relation', relation_id),), limit=1)
    element = elements[0]
    await ElementMemberQuery.resolve_members(elements)

    assert not element.members


async def test_members_invalid_not_found(changeset_id: int):
    element = Element(
        changeset_id=changeset_id,
        type='relation',
        id=-1,
        version=1,
        visible=True,
        tags={},
        point=None,
        members=[ElementMember(order=0, type='node', id=-1, role='')],
    )

    with pytest.raises(Exception):
        await OptimisticDiff.run((element,))


async def test_members_invalid_deleted(changeset_id: int):
    elements = (
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=2,
            visible=False,
            tags={},
            point=None,
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='way',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=None,
            members=[ElementMember(order=0, type='node', id=-1, role='')],
        ),
    )

    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_members_invalid_delete(changeset_id: int):
    elements = (
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='way',
            id=-1,
            version=1,
            visible=True,
            tags={},
            point=None,
            members=[ElementMember(order=0, type='node', id=-1, role='')],
        ),
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=2,
            visible=False,
            tags={},
            point=None,
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='way',
            id=-1,
            version=2,
            visible=False,
            tags={},
            point=None,
            members=[],
        ),
    )

    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)
