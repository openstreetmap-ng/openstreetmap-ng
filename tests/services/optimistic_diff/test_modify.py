import pytest
from shapely import Point

from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff


async def test_modify_simple(changeset_id: int):
    elements = (
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=1,
            visible=True,
            tags={'created': 'yes'},
            point=Point(0, 0),
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-1,
            version=2,
            visible=True,
            tags={'modified': 'yes'},
            point=Point(1, 2),
            members=[],
        ),
    )

    assigned_ref_map = await OptimisticDiff.run(elements)
    node_id = assigned_ref_map[ElementRef('node', -1)][0].id

    elements = await ElementQuery.get_by_refs((ElementRef('node', node_id),), limit=1)
    element = elements[0]
    await ElementMemberQuery.resolve_members(elements)

    assert element.changeset_id == changeset_id
    assert element.type == 'node'
    assert element.id > 0
    assert element.version == 2
    assert element.visible
    assert element.tags == {'modified': 'yes'}
    assert element.point == Point(1, 2)
    assert element.members is None


async def test_modify_invalid_id(changeset_id: int):
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
            id=-2,
            version=2,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
        Element(
            changeset_id=changeset_id,
            type='node',
            id=-2,
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
    )

    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_modify_invalid_version_gap(changeset_id: int):
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
            version=3,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
    )

    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)
