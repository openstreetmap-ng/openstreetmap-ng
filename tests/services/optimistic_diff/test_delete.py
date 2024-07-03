import pytest
from shapely import Point

from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element_ref import ElementRef
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff


async def test_delete_if_unused(changeset_id: int):
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
            delete_if_unused=True,
        ),
    )

    assigned_ref_map = await OptimisticDiff.run(elements)
    assert len(assigned_ref_map[ElementRef('node', -1)]) == 1
    assert len(assigned_ref_map[ElementRef('way', -1)]) == 1
    node_id = assigned_ref_map[ElementRef('node', -1)][0].id

    elements = await ElementQuery.get_by_refs((ElementRef('node', node_id),), limit=1)
    element = elements[0]

    assert element.version == 1


async def test_delete_invalid_repeated(changeset_id: int):
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
            type='node',
            id=-1,
            version=3,
            visible=False,
            tags={},
            point=None,
            members=[],
        ),
    )

    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)
