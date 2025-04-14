import pytest
from shapely import Point

from app.models.db.element import ElementInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff import OptimisticDiff
from tests.utils.assert_model import assert_model


async def test_modify_node_tags_and_location(changeset_id: ChangesetId):
    # Create a node element
    node_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'created': 'yes'},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Modify the node's tags and location
    node_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'modified': 'yes'},
        'point': Point(1, 2),
        'members': None,
        'members_roles': None,
    }

    # Push elements to the database
    assigned_ref_map = await OptimisticDiff.run([node_create, node_modify])

    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Verify the modified element
    elements = await ElementQuery.get_by_refs([node_typed_id], limit=1)
    assert_model(elements[0], node_modify | {'typed_id': node_typed_id})


async def test_modify_way_members(changeset_id: ChangesetId):
    # Create two node elements
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

    # Create a way with one node
    way_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'highway': 'residential'},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': None,
    }

    # Modify the way to include both nodes
    way_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('way', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'highway': 'residential', 'modified': 'yes'},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('node', ElementId(-2)),
        ],
        'members_roles': None,
    }

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run([node1, node2, way_create, way_modify])

    node1_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    node2_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-2))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]

    # Verify the modified way
    elements = await ElementQuery.get_by_refs([way_typed_id], limit=1)
    assert_model(
        elements[0],
        way_modify
        | {
            'typed_id': way_typed_id,
            'members': [node1_typed_id, node2_typed_id],
        },
    )


async def test_modify_relation_members_and_roles(changeset_id: ChangesetId):
    # Create a node and a way
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

    # Create a relation with just the node
    relation_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {'type': 'test'},
        'point': None,
        'members': [typed_element_id('node', ElementId(-1))],
        'members_roles': ['old_role'],
    }

    # Modify the relation to include both node and way with different roles
    relation_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('relation', ElementId(-1)),
        'version': 2,
        'visible': True,
        'tags': {'type': 'test', 'modified': 'yes'},
        'point': None,
        'members': [
            typed_element_id('node', ElementId(-1)),
            typed_element_id('way', ElementId(-1)),
        ],
        'members_roles': ['new_node_role', 'way_role'],
    }

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run([
        node,
        way,
        relation_create,
        relation_modify,
    ])

    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    way_typed_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    relation_typed_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]

    # Verify the modified relation
    elements = await ElementQuery.get_by_refs([relation_typed_id], limit=1)
    assert_model(
        elements[0],
        relation_modify
        | {
            'typed_id': relation_typed_id,
            'members': [node_typed_id, way_typed_id],
        },
    )


async def test_invalid_version_gap(changeset_id: ChangesetId):
    # Create a node element
    node_create: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 1,
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Try to modify the node with a version gap (skipping version 2)
    node_modify: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': typed_element_id('node', ElementId(-1)),
        'version': 3,  # Invalid: should be 2
        'visible': True,
        'tags': {},
        'point': Point(0, 0),
        'members': None,
        'members_roles': None,
    }

    # Operation must fail due to version gap
    with pytest.raises(Exception):
        await OptimisticDiff.run([node_create, node_modify])


async def test_multiple_consecutive_modifications(changeset_id: ChangesetId):
    # Create elements for multiple versions of a node
    nodes: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-1)),
            'version': i,
            'visible': True,
            'tags': {'version': str(i)},
            'point': Point(i, i),
            'members': None,
            'members_roles': None,
        }
        for i in range(1, 4)
    ]

    # Push all elements to the database
    assigned_ref_map = await OptimisticDiff.run(nodes)
    node_typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Verify each version
    elements = await ElementQuery.get_versions_by_ref(node_typed_id, sort_dir='asc')
    for element, node in zip(elements, nodes, strict=True):
        assert_model(element, node | {'typed_id': node_typed_id})
