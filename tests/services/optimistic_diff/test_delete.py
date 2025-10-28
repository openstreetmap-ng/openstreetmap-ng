import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff
from speedup.element_type import typed_element_id
from tests.utils.assert_model import assert_model


async def test_delete_node(changeset_id: ChangesetId):
    # Create element
    node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'name': 'Test Node'},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    assigned_ref_map = await OptimisticDiff.run([node])
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Delete element
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_id,
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }
    await OptimisticDiff.run([node_delete])

    # Verify deletion
    elements = await ElementQuery.find_by_refs([typed_id], limit=1)
    assert_model(elements[0], node_delete)


async def test_delete_way_with_node_members(changeset_id: ChangesetId):
    # Create elements
    node1: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node2: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-2)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(1, 1),
        'members': None,
        'members_roles': None,
    }
    way: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'highway': 'residential'},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('node', ElementId(-2)),
        ],
        'members_roles': None,
    }
    assigned_ref_map = await OptimisticDiff.run([node1, node2, way])
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Delete way
    way_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': way_typed_id,
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }
    await OptimisticDiff.run([way_delete])

    # Verify deletion
    elements = await ElementQuery.find_by_refs([way_typed_id], limit=1)
    assert_model(elements[0], way_delete)


async def test_delete_if_unused_skips_deletion_when_still_referenced(
    changeset_id: ChangesetId,
):
    # Arrange
    node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    way: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
        'delete_if_unused': True,
    }

    # Act
    assigned_ref_map = await OptimisticDiff.run([node, way, node_delete])

    # Assert - node remains visible (deletion skipped)
    typed_id_node = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    elements = await ElementQuery.find_by_refs([typed_id_node], limit=1)
    assert_model(elements[0], node | {'typed_id': typed_id_node})


async def test_delete_fails_when_referenced_without_delete_if_unused_flag(
    changeset_id: ChangesetId,
):
    # Arrange
    node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    way: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([node, way, node_delete])


async def test_delete_fails_when_repeated_in_same_batch(changeset_id: ChangesetId):
    # Arrange
    node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    node_delete1: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }
    node_delete2: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 3,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([node, node_delete1, node_delete2])


async def test_delete_fails_for_nonexistent_element(changeset_id: ChangesetId):
    # Arrange
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId((1 << 56) - 1)),
        'version': 2,
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Act & Assert
    with pytest.raises(Exception):
        await OptimisticDiff.run([node_delete])


async def test_delete_fails_with_wrong_version(changeset_id: ChangesetId):
    # Create element
    node: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }
    assigned_ref_map = await OptimisticDiff.run([node])
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Attempt deletion with wrong version
    node_delete: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_id,
        'version': 3,  # Should be 2
        'visible': False,
        'tags': None,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    with pytest.raises(Exception):
        await OptimisticDiff.run([node_delete])
