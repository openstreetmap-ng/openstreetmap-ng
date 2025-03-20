import pytest
from shapely import Point

from app.lib.user_role_limits import UserRoleLimits
from app.models.db.element import ElementInit, validate_elements
from app.models.element import ElementId, ElementType, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.changeset_service import ChangesetService
from app.services.optimistic_diff import OptimisticDiff
from tests.utils.assert_model import assert_model


async def test_create_node(changeset_id: ChangesetId):
    # Create a simple node element
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

    # Push changes to the database
    assigned_ref_map = await OptimisticDiff.run([element])
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Verify the created element
    elements = await ElementQuery.get_by_refs([typed_id], limit=1)
    assert_model(elements[0], element | {'typed_id': typed_id})


async def test_create_node_with_tags(changeset_id: ChangesetId):
    # Create a node with tags
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

    # Push changes to the database
    assigned_ref_map = await OptimisticDiff.run([element])
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Verify the created element
    elements = await ElementQuery.get_by_refs([typed_id], limit=1)
    assert_model(elements[0], element | {'typed_id': typed_id})


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
async def test_create_with_nonexistent_members(changeset_id: ChangesetId, element_type: ElementType, members):
    # Create a way or relation with members
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

    # Should fail because the referenced elements don't exist
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


async def test_create_with_zero_changeset_id():
    # Create element with invalid changeset id
    element: ElementInit = {
        'changeset_id': ChangesetId(0),  # Invalid changeset id
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to invalid changeset id
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


async def test_create_with_multiple_changesets(changeset_id: ChangesetId):
    # Create elements with different changesets
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
            'changeset_id': ChangesetId(changeset_id - 1),  # Different changeset
            'typed_id': typed_element_id('node', ElementId(-2)),
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(1, 1),
            'members': None,
            'members_roles': None,
        },
    ]

    # Operation must fail due to different changeset ids
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_create_with_positive_id(changeset_id: ChangesetId):
    # Create element with positive id (should be negative for new elements)
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(1)),  # Positive id is invalid for creation
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to invalid element id
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


@pytest.mark.extended
async def test_create_exceeding_changeset_size(changeset_id: ChangesetId):
    # Create more elements than the changeset can handle
    max_size = UserRoleLimits.get_changeset_max_size(None)

    elements: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-i)),
            'version': 1,
            'visible': True,
            'tags': {},
            'point': Point(i % 10, i // 10),  # Distribute points on a grid
            'members': None,
            'members_roles': None,
        }
        for i in range(1, max_size + 2)  # One more than the limit
    ]

    # Operation must fail due to changeset size limit
    with pytest.raises(Exception):
        await OptimisticDiff.run(elements)


async def test_create_with_closed_changeset(changeset_id: ChangesetId):
    # Close the changeset first
    await ChangesetService.close(changeset_id)

    # Try to create an element with a closed changeset
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

    # Operation must fail due to closed changeset
    with pytest.raises(Exception):
        await OptimisticDiff.run([element])


async def test_create_multiple_nodes(changeset_id: ChangesetId):
    # Create multiple elements in a single operation
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

    # Push changes to the database
    assigned_ref_map = await OptimisticDiff.run(nodes)

    typed_ids = [
        assigned_ref_map[typed_element_id('node', ElementId(-1))][0],
        assigned_ref_map[typed_element_id('node', ElementId(-2))][0],
    ]

    # Verify the created elements
    elements = await ElementQuery.get_by_refs(typed_ids)
    name_map = {e['tags']['name']: e for e in elements}  # type: ignore
    assert_model(name_map['Node 1'], nodes[0] | {'typed_id': typed_ids[0]})
    assert_model(name_map['Node 2'], nodes[1] | {'typed_id': typed_ids[1]})


def test_create_hidden(changeset_id: ChangesetId):
    # Try to create an element with visible=False (invalid for version 1)
    element: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': False,  # Cannot create invisible elements
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to creation of invisible element
    with pytest.raises(Exception):
        validate_elements([element])
