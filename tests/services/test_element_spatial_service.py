import pytest
from shapely import LineString, Point, box

from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from app.queries.element_spatial_query import ElementSpatialQuery
from app.services.element_spatial_service import ElementSpatialService
from app.services.optimistic_diff import OptimisticDiff
from app.validators.geometry import validate_geometry
from speedup.element_type import typed_element_id


@pytest.mark.extended
async def test_element_spatial_cascading_updates(changeset_id: ChangesetId):
    """
    Test element_spatial cascading updates.
    Structure: 2 nodes -> 1 way -> relation1 -> relation2
    Verifies initial materialization and update propagation.
    """
    # Arrange: Create cascading structure in single operation
    elements: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-1)),
            'version': 1,
            'visible': True,
            'tags': {'name': 'Node 1'},
            'point': Point(10, 10),
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-2)),
            'version': 1,
            'visible': True,
            'tags': {'name': 'Node 2'},
            'point': Point(10.001, 10),
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('way', ElementId(-1)),
            'version': 1,
            'visible': True,
            'tags': {'highway': 'residential', 'name': 'Test Way'},
            'point': None,
            'members': [
                typed_element_id('node', ElementId(-1)),
                typed_element_id('node', ElementId(-2)),
            ],
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('relation', ElementId(-1)),
            'version': 1,
            'visible': True,
            'tags': {'type': 'route', 'name': 'Relation 1'},
            'point': None,
            'members': [typed_element_id('way', ElementId(-1))],
            'members_roles': ['outer'],
        },
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('relation', ElementId(-2)),
            'version': 1,
            'visible': True,
            'tags': {'type': 'superroute', 'name': 'Relation 2'},
            'point': None,
            'members': [typed_element_id('relation', ElementId(-1))],
            'members_roles': [''],
        },
    ]

    assigned_ref_map = await OptimisticDiff.run(elements)
    node1_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]
    node2_id = assigned_ref_map[typed_element_id('node', ElementId(-2))][0]
    way_id = assigned_ref_map[typed_element_id('way', ElementId(-1))][0]
    relation1_id = assigned_ref_map[typed_element_id('relation', ElementId(-1))][0]
    relation2_id = assigned_ref_map[typed_element_id('relation', ElementId(-2))][0]

    # Act: Process element_spatial
    await ElementSpatialService.force_process()

    # Assert: Verify initial materialization
    search_area = validate_geometry(box(9.999, 9.999, 10.002, 10.001))

    results = await ElementSpatialQuery.query_features(search_area)
    results_by_id = {r['typed_id']: r for r in results}

    assert node1_id in results_by_id, 'Node 1 not found'
    assert node2_id in results_by_id, 'Node 2 not found'
    assert way_id in results_by_id, 'Way not found'
    assert relation1_id in results_by_id, 'Relation 1 not found'
    assert relation2_id in results_by_id, 'Relation 2 not found'

    assert results_by_id[node1_id]['geom'].equals_exact(Point(10, 10), 1e-7), (
        'Node 1 geometry incorrect'
    )
    assert results_by_id[node2_id]['geom'].equals_exact(Point(10.001, 10), 1e-7), (
        'Node 2 geometry incorrect'
    )

    expected_way_geom = LineString([(10, 10), (10.001, 10)])
    assert results_by_id[way_id]['geom'].equals_exact(expected_way_geom, 1e-7), (
        'Way geometry incorrect'
    )
    assert results_by_id[relation1_id]['geom'].equals_exact(expected_way_geom, 1e-7), (
        'Relation 1 geometry incorrect'
    )
    assert results_by_id[relation2_id]['geom'].equals_exact(expected_way_geom, 1e-7), (
        'Relation 2 geometry incorrect'
    )

    # Update: Modify node1 to trigger cascade
    node1_update: ElementInit = {
        'changeset_id': changeset_id,
        'typed_id': node1_id,
        'version': 2,
        'visible': True,
        'tags': {'name': 'Node 1 Updated'},
        'point': Point(10.0005, 10.0005),
        'members': None,
        'members_roles': None,
    }

    await OptimisticDiff.run([node1_update])
    await ElementSpatialService.force_process()

    # Assert: Verify cascade propagated
    results_after = await ElementSpatialQuery.query_features(search_area)
    results_after_by_id = {r['typed_id']: r for r in results_after}

    assert node1_id in results_after_by_id, 'Node 1 not found'
    assert node2_id in results_after_by_id, 'Node 2 not found'
    assert way_id in results_after_by_id, 'Way not found'
    assert relation1_id in results_after_by_id, 'Relation 1 not found'
    assert relation2_id in results_after_by_id, 'Relation 2 not found'

    assert results_after_by_id[node1_id]['geom'].equals_exact(
        Point(10.0005, 10.0005), 1e-7
    ), 'Node 1 geometry incorrect'
    assert results_after_by_id[node2_id]['geom'].equals_exact(
        Point(10.001, 10), 1e-7
    ), 'Node 2 geometry incorrect'

    expected_updated_way_geom = LineString([(10.0005, 10.0005), (10.001, 10)])
    assert results_after_by_id[way_id]['geom'].equals_exact(
        expected_updated_way_geom, 1e-7
    ), 'Way geometry incorrect'
    assert results_after_by_id[relation1_id]['geom'].equals_exact(
        expected_updated_way_geom, 1e-7
    ), 'Relation 1 geometry incorrect'
    assert results_after_by_id[relation2_id]['geom'].equals_exact(
        expected_updated_way_geom, 1e-7
    ), 'Relation 2 geometry incorrect'

    # Delete: Remove all elements
    deletes: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': relation2_id,
            'version': 2,
            'visible': False,
            'tags': None,
            'point': None,
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': relation1_id,
            'version': 2,
            'visible': False,
            'tags': None,
            'point': None,
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': way_id,
            'version': 2,
            'visible': False,
            'tags': None,
            'point': None,
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': node1_id,
            'version': 3,
            'visible': False,
            'tags': None,
            'point': None,
            'members': None,
            'members_roles': None,
        },
        {
            'changeset_id': changeset_id,
            'typed_id': node2_id,
            'version': 2,
            'visible': False,
            'tags': None,
            'point': None,
            'members': None,
            'members_roles': None,
        },
    ]

    await OptimisticDiff.run(deletes)
    await ElementSpatialService.force_process()

    # Assert: Verify cleanup
    results_deleted = await ElementSpatialQuery.query_features(search_area)
    result_ids_deleted = {r['typed_id'] for r in results_deleted}

    assert node1_id not in result_ids_deleted, 'Node 1 not deleted'
    assert node2_id not in result_ids_deleted, 'Node 2 not deleted'
    assert way_id not in result_ids_deleted, 'Way not deleted'
    assert relation1_id not in result_ids_deleted, 'Relation 1 not deleted'
    assert relation2_id not in result_ids_deleted, 'Relation 2 not deleted'
