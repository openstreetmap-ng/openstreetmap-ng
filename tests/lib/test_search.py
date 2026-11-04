from shapely import Point

from app.lib.text.search import Search, SearchResult
from app.models.element import ElementId
from app.models.types import ChangesetId
from speedup import typed_element_id


def _create_search_result(
    *,
    osm_type: str,
    id_: int,
    tags: dict[str, str],
    display_name: str,
    lon: float,
    lat: float,
    bounds: tuple[float, float, float, float],
    rank: int = 26,
    importance: float = 0.5,
) -> SearchResult:
    element = {
        'changeset_id': ChangesetId(1),
        'typed_id': typed_element_id(osm_type, ElementId(id_)),
        'version': 1,
        'visible': True,
        'tags': tags,
        'point': Point(lon, lat),
        'members': None,
        'members_roles': None,
    }
    return SearchResult(
        element=element,  # type: ignore
        rank=rank,
        importance=importance,
        icon=None,
        prefix='Road',
        display_name=display_name,
        point=Point(lon, lat),
        bounds=bounds,
    )


def test_deduplicate_street_ways_same_name_merges_bounds():
    # Two ways representing segments of the same street within 1km of each other
    r1 = _create_search_result(
        osm_type='way',
        id_=101,
        tags={'highway': 'trunk', 'name': 'Vasil Levski Blvd'},
        display_name='Vasil Levski Blvd, Varna 9010, Bulgaria',
        lon=27.917,
        lat=43.220,
        bounds=(27.916, 43.219, 27.918, 43.221),
        importance=0.6,
    )
    r2 = _create_search_result(
        osm_type='way',
        id_=102,
        tags={'highway': 'trunk', 'name': 'Vasil Levski Blvd'},
        display_name='Vasil Levski Blvd, Varna 9015, Bulgaria',
        lon=27.925,
        lat=43.225,
        bounds=(27.920, 43.222, 27.930, 43.228),
        importance=0.4,
    )

    results = Search.deduplicate_similar_results([r1, r2])
    assert len(results) == 1
    assert results[0].element['typed_id'] == r1.element['typed_id']
    # Merged bounds encompass both segments
    assert results[0].bounds == (27.916, 43.219, 27.930, 43.228)


def test_deduplicate_street_prefers_road_relation_over_way():
    # Way of the street followed by the road relation representing the entire route
    way_result = _create_search_result(
        osm_type='way',
        id_=201,
        tags={'highway': 'primary', 'name': 'Main Street'},
        display_name='Main Street, Cityville 10001, USA',
        lon=-73.985,
        lat=40.748,
        bounds=(-73.986, 40.747, -73.984, 40.749),
        importance=0.5,
    )
    relation_result = _create_search_result(
        osm_type='relation',
        id_=501,
        tags={'type': 'route', 'route': 'road', 'name': 'Main Street'},
        display_name='Main Street, Cityville, USA',
        lon=-73.982,
        lat=40.750,
        bounds=(-73.990, 40.740, -73.970, 40.760),
        importance=0.45,
    )

    results = Search.deduplicate_similar_results([way_result, relation_result])
    # The road relation must be preferred over the individual way
    assert len(results) == 1
    assert results[0].element['typed_id'] == relation_result.element['typed_id']
    # Bounds should include the way's bounds as well
    assert results[0].bounds == (-73.990, 40.740, -73.970, 40.760)


def test_street_deduplication_different_names_preserved():
    # Two adjacent streets with different names
    r1 = _create_search_result(
        osm_type='way',
        id_=301,
        tags={'highway': 'residential', 'name': 'First Avenue'},
        display_name='First Avenue, Springfield, USA',
        lon=-89.650,
        lat=39.780,
        bounds=(-89.651, 39.779, -89.649, 39.781),
    )
    r2 = _create_search_result(
        osm_type='way',
        id_=302,
        tags={'highway': 'residential', 'name': 'Second Avenue'},
        display_name='Second Avenue, Springfield, USA',
        lon=-89.651,
        lat=39.781,
        bounds=(-89.652, 39.780, -89.650, 39.782),
    )

    results = Search.deduplicate_similar_results([r1, r2])
    assert len(results) == 2


def test_street_deduplication_distant_same_name_preserved():
    # Two streets with the same common name in different cities (>50km apart)
    r1 = _create_search_result(
        osm_type='way',
        id_=401,
        tags={'highway': 'residential', 'name': 'High Street'},
        display_name='High Street, City A, UK',
        lon=-0.12,
        lat=51.50,
        bounds=(-0.13, 51.49, -0.11, 51.51),
    )
    r2 = _create_search_result(
        osm_type='way',
        id_=402,
        tags={'highway': 'residential', 'name': 'High Street'},
        display_name='High Street, City B, UK',
        lon=-1.54,
        lat=53.80,
        bounds=(-1.55, 53.79, -1.53, 53.81),
    )

    results = Search.deduplicate_similar_results([r1, r2])
    assert len(results) == 2
