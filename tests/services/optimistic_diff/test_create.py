import pytest
from shapely import Point

from app.lib.user_role_limits import UserRoleLimits
from app.models.db.element import ElementInit, validate_elements
from app.models.element import ElementId, ElementType
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.changeset_service import ChangesetService
from app.services.optimistic_diff import OptimisticDiff
from speedup import typed_element_id
from tests.utils.assert_model import assert_model


async def test_create_node(changeset_id: ChangesetId):
    # Arrange
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([element])

    # Assert
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([typed_id], limit=1)
    assert_model(elements[0], element | {'typed_id': typed_id})


async def test_create_node_with_tags(changeset_id: ChangesetId):
    # Arrange
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'name': 'Test Node', 'amenity': 'cafe'},
        'point': Point(1.5, 2.5),
        'members': None,
        'members_roles': None,
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([element])

    # Assert
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([typed_id], limit=1)
    assert_model(elements[0], element | {'typed_id': typed_id})


async def test_create_multiple_nodes(changeset_id: ChangesetId):
    # Arrange
    nodes: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-1)),
            'version': 1,
            'visible': True,
            'tags': {'name': 'Node 1'},
            'point': Point(0, 0),
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-2)),
            'version': 1,
            'visible': True,
            'tags': {'name': 'Node 2'},
            'point': Point(1, 1),
            'members': None,
            'members_roles': None,
        },
    ]

    # Act
    assigned_ref_map = await OptimisticDiff.run(nodes)

    # Assert
    typed_ids = [
        assigned_ref_map[typed_element_id('node', ElementId(-1))][0],
        assigned_ref_map[typed_element_id('node', ElementId(-2))][0],
    ]
    elements = await ElementQuery.find_by_refs(typed_ids)
    name_map = {e['tags']['name']: e for e in elements}  # type: ignore
    assert_model(name_map['Node 1'], nodes[0] | {'typed_id': typed_ids[0]})
    assert_model(name_map['Node 2'], nodes[1] | {'typed_id': typed_ids[1]})


@pytest.mark.parametrize(
    ('element_type', 'members'),
    [
        (
            'way',
            [
                typed_element_id('node', ElementId((1 << 56) - 1)),
                typed_element_id('node', ElementId((1 << 56) - 2)),
            ],
        ),
        (
            'relation',
            [
                typed_element_id('node', ElementId((1 << 56) - 1)),
                typed_element_id('way', ElementId((1 << 56) - 1)),
            ],
        ),
    ],
)
async def test_create_fails_with_nonexistent_members(
    changeset_id: ChangesetId, element_type: ElementType, members
):
    # Arrange
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id(element_type, ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': members,
        'members_roles': [''] * len(members) if element_type == 'relation' else None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


async def test_create_fails_with_zero_changeset_id():
    # Arrange
    element: ElementInit = {
        'changeset_id': ChangesetId(0),
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


async def test_create_fails_with_multiple_changesets(changeset_id: ChangesetId):
    # Arrange
    elements: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-1)),
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(0, 0),
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': ChangesetId(changeset_id - 1),
            'typed_id': typed_element_id('node', ElementId(-2)),
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(1, 1),
            'members': None,
            'members_roles': None,
        },
    ]

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_create_fails_with_positive_id(changeset_id: ChangesetId):
    # Arrange
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


async def test_create_fails_with_closed_changeset(changeset_id: ChangesetId):
    # Arrange
    await ChangesetService.close(changeset_id)
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


def test_create_fails_when_invisible(changeset_id: ChangesetId):
    # Arrange
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': False,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        validate_elements([element])


@pytest.mark.extended
async def test_create_fails_when_exceeding_changeset_size(changeset_id: ChangesetId):
    # Arrange
    max_size = UserRoleLimits.get_changeset_max_size(None)
    elements: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-i)),
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(i % 10, i // 10),
            'members': None,
            'members_roles': None,
        }
        for i in range(1, max_size + 2)
    ]

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)
