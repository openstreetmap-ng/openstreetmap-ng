import pytest
from shapely import Point

from app.lib.user_role_limits import UserRoleLimits
from app.models.db.element import Element
from app.models.element import ElementId, ElementRef
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.services.changeset_service import ChangesetService
from app.services.optimistic_diff import OptimisticDiff


async def test_create_simple(changeset_id: int):
    element = Element(
        changeset_id=changeset_id,
        type='node',
        id=ElementId(-1),
        version=1,
        visible=True,
        tags={},
        point=Point(0, 0),
        members=[],
    )

    assigned_ref_map = await OptimisticDiff.run((element,))
    node_id = assigned_ref_map[ElementRef('node', ElementId(-1))][0].id

    elements = await ElementQuery.get_by_refs((ElementRef('node', node_id),), limit=1)
    element = elements[0]
    await ElementMemberQuery.resolve_members(elements)

    assert element.changeset_id == changeset_id
    assert element.type == 'node'
    assert element.id > 0
    assert element.version == 1
    assert element.visible
    assert element.tags == {}
    assert element.point == Point(0, 0)
    assert not element.members


async def test_create_invalid_changeset_id():
    element = Element(
        changeset_id=0,
        type='node',
        id=ElementId(-1),
        version=1,
        visible=True,
        tags={},
        point=Point(0, 0),
        members=[],
    )
    with pytest.raises(Exception):
        await OptimisticDiff.run((element,))


async def test_create_invalid_multiple_changesets(changeset_id: int):
    elements = (
        Element(
            changeset_id=changeset_id,
            type='node',
            id=ElementId(-1),
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
        Element(
            changeset_id=changeset_id - 1,
            type='node',
            id=ElementId(-2),
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        ),
    )
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_create_invalid_id(changeset_id: int):
    element = Element(
        changeset_id=changeset_id,
        type='node',
        id=ElementId(1),
        version=1,
        visible=True,
        tags={},
        point=Point(0, 0),
        members=[],
    )
    with pytest.raises(Exception):
        await OptimisticDiff.run((element,))


@pytest.mark.extended
async def test_create_invalid_changeset_size(changeset_id: int):
    elements = tuple(
        Element(
            changeset_id=changeset_id,
            type='node',
            id=ElementId(i),
            version=1,
            visible=True,
            tags={},
            point=Point(0, 0),
            members=[],
        )
        for i in range(-1, -UserRoleLimits.get_changeset_max_size(()) - 2, -1)
    )
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_create_invalid_changeset_closed(changeset_id: int):
    await ChangesetService.close(changeset_id)
    element = Element(
        changeset_id=changeset_id,
        type='node',
        id=ElementId(-1),
        version=1,
        visible=True,
        tags={},
        point=Point(0, 0),
        members=[],
    )
    with pytest.raises(Exception):
        await OptimisticDiff.run((element,))
