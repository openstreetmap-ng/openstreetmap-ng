from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cython
import numpy as np
from shapely import MultiPolygon, Point, Polygon, STRtree

from app.models.element import TypedElementId
from speedup import element_type

if TYPE_CHECKING:
    from app.models.proto.shared_pb2 import Bounds

    from app.lib.text.feature_icon import FeatureIcon
    from app.models.db.element import Element

if cython.compiled:
    from cython.cimports.libc.math import ceil, log2
else:
    from math import ceil, log2


@dataclass(kw_only=True, slots=True)
class SearchResult:
    element: Element
    rank: int  # for determining global vs local relevance
    importance: float  # for sorting results
    icon: FeatureIcon | None
    prefix: str
    display_name: str
    point: Point
    bounds: tuple[float, float, float, float]


class Search:
    @staticmethod
    def get_search_bounds(
        bbox: Bounds,
        *,
        local_only: bool = False,
        local_max_iterations: int | None = None,
    ):
        """
        Get search bounds from a bbox.

        Returns a list of (Bounds, shapely) bounds.
        """
        from app.models.proto.shared_pb2 import Bounds  # noqa: PLC0415

        from app.config import (  # noqa: PLC0415
            SEARCH_LOCAL_AREA_LIMIT,
            SEARCH_LOCAL_MAX_ITERATIONS,
        )
        from app.lib.geo.parse import parse_bbox  # noqa: PLC0415

        search_local_area_limit: cython.double = SEARCH_LOCAL_AREA_LIMIT
        search_local_max_iterations: cython.size_t = (
            local_max_iterations
            if local_max_iterations is not None
            else SEARCH_LOCAL_MAX_ITERATIONS
        )

        minx: cython.double = bbox.min_lon
        miny: cython.double = bbox.min_lat
        maxx: cython.double = bbox.max_lon
        maxy: cython.double = bbox.max_lat

        bbox_width = maxx - minx
        bbox_width_2 = bbox_width / 2
        bbox_height = maxy - miny
        bbox_height_2 = bbox_height / 2
        bbox_area = bbox_width * bbox_height

        bbox_center_x = minx + bbox_width_2
        bbox_center_y = miny + bbox_height_2

        local_iterations: cython.ssize_t = (
            1 if local_only else int(ceil(log2(search_local_area_limit / bbox_area)))  # noqa: RUF046
        )
        local_iterations = max(1, min(local_iterations, search_local_max_iterations))

        logging.debug(
            'Searching area of %g with %d local iterations', bbox_area, local_iterations
        )
        result: list[tuple[Bounds, Polygon | MultiPolygon] | tuple[None, None]]
        result = [None] * local_iterations  # type: ignore

        i: cython.size_t
        for i in range(local_iterations):
            bounds_width_2 = bbox_width_2 * (2**i)
            bounds_height_2 = bbox_height_2 * (2**i)
            bounds_minx = bbox_center_x - bounds_width_2
            bounds_miny = bbox_center_y - bounds_height_2
            bounds_maxx = bbox_center_x + bounds_width_2
            bounds_maxy = bbox_center_y + bounds_height_2
            result[i] = (
                Bounds(
                    min_lon=bounds_minx,
                    min_lat=bounds_miny,
                    max_lon=bounds_maxx,
                    max_lat=bounds_maxy,
                ),
                parse_bbox((
                    bounds_minx,
                    bounds_miny,
                    bounds_maxx,
                    bounds_maxy,
                )),
            )

        if not local_only:
            # append global search bounds
            result.append((None, None))

        return result

    @staticmethod
    def best_results_index(task_results: list[list[SearchResult]]):
        """Determine the best results index."""
        # local_only mode
        if len(task_results) == 1:
            return 0

        if _should_use_global_search(task_results):
            # global search
            logging.debug('Search performed using global mode')
            return -1

        from app.config import SEARCH_LOCAL_RATIO  # noqa: PLC0415

        logging.debug('Search performed using local mode')
        max_local_results: cython.size_t = len(task_results[-2])
        search_local_ratio: cython.double = SEARCH_LOCAL_RATIO
        threshold = max_local_results * search_local_ratio

        # zoom out until there are enough local results
        for i, results in enumerate(task_results[:-2]):
            if len(results) >= threshold:
                return i

        return -2

    @staticmethod
    def improve_point_accuracy(
        results: list[SearchResult], members_map: dict[TypedElementId, Element]
    ):
        """Improve accuracy of points by analyzing relations members."""
        for result in results:
            if element_type(result.element['typed_id']) != 'relation':
                continue

            element = result.element
            members_tids = element['members']
            assert members_tids is not None, 'Relation members must be set'
            members_roles = element['members_roles']
            assert members_roles is not None, 'Relation members roles must be set'

            success: cython.bint = False
            for member_tid, role in zip(members_tids, members_roles):
                if element_type(member_tid) != 'node' or (
                    success and role != 'admin_centre'
                ):
                    continue

                member = members_map.get(member_tid)
                if member is None or (point := member['point']) is None:
                    continue

                result.point = point
                success = True

    @staticmethod
    def remove_overlapping_points(results: list[SearchResult]):
        """Remove overlapping points, preserving most important results."""
        relations = [
            result
            for result in results
            if element_type(result.element['typed_id']) == 'relation'
        ]
        if len(relations) <= 1:
            return

        geoms = [result.point for result in relations]
        tree = STRtree(geoms)

        nearby_all = tree.query(geoms, 'dwithin', 0.001).T
        nearby_all = np.unique(nearby_all, axis=0)
        nearby_all = nearby_all[nearby_all[:, 0] < nearby_all[:, 1]]
        nearby_all = np.sort(nearby_all, axis=1)

        for i1, i2 in nearby_all.tolist():
            if relations[i1].point is not None:
                relations[i2].point = None

    @staticmethod
    def deduplicate_similar_results(results: list[SearchResult]):
        """Deduplicate similar results."""
        # Deduplicate by type and id
        seen: set[TypedElementId] = set()
        dedup1: list[SearchResult] = []
        geoms: list[Point] = []
        for result in results:
            typed_id = result.element['typed_id']
            if typed_id not in seen:
                seen.add(typed_id)
                dedup1.append(result)
                geoms.append(result.point)

        num_geoms: cython.size_t = len(geoms)
        if num_geoms <= 1:
            return dedup1

        # Deduplicate by location and name
        tree = STRtree(geoms)

        nearby_all = tree.query(geoms, 'dwithin', 0.001).T
        nearby_all = np.unique(nearby_all, axis=0)
        nearby_all = nearby_all[nearby_all[:, 0] < nearby_all[:, 1]]
        nearby_all = np.sort(nearby_all, axis=1)

        mask = [True] * num_geoms
        for i1, i2 in nearby_all.tolist():
            if not mask[i1]:
                continue
            name1 = dedup1[i1].display_name
            name2 = dedup1[i2].display_name
            if name1 == name2:
                mask[i2] = False

        # Deduplicate streets with same name in vicinity (~5.5 km), preferring road relations
        street_proximity: cython.double = 0.05
        nearby_streets = tree.query(geoms, 'dwithin', street_proximity).T
        nearby_streets = np.unique(nearby_streets, axis=0)
        nearby_streets = nearby_streets[nearby_streets[:, 0] < nearby_streets[:, 1]]
        nearby_streets = np.sort(nearby_streets, axis=1)

        for i1, i2 in nearby_streets.tolist():
            if not mask[i1] and not mask[i2]:
                continue
            r1 = dedup1[i1]
            r2 = dedup1[i2]
            if not (_is_street(r1.element) and _is_street(r2.element)):
                continue

            street_name1 = _get_street_name(r1)
            street_name2 = _get_street_name(r2)
            if (
                street_name1 is not None
                and street_name2 is not None
                and street_name1.casefold() == street_name2.casefold()
            ):
                is_rel1 = element_type(r1.element['typed_id']) == 'relation'
                is_rel2 = element_type(r2.element['typed_id']) == 'relation'

                if is_rel2 and not is_rel1 and mask[i2]:
                    mask[i1] = False
                    r2.bounds = _merge_bounds(r2.bounds, r1.bounds)
                elif mask[i1]:
                    mask[i2] = False
                    r1.bounds = _merge_bounds(r1.bounds, r2.bounds)
                elif mask[i2]:
                    r2.bounds = _merge_bounds(r2.bounds, r1.bounds)

        return [result for result, is_mask in zip(dedup1, mask) if is_mask]


@cython.cfunc
def _should_use_global_search(task_results: list[list[SearchResult]]) -> cython.bint:
    """
    Determine whether to use global search or local search.
    Global search is used when there are no relevant local results.
    """
    local_results = task_results[:-1]
    if not any(local_results):
        return True

    global_results = task_results[-1]
    if not global_results:
        return False

    # https://nominatim.org/release-docs/latest/customize/Ranking/
    return global_results[0].rank <= 16


def _merge_bounds(
    b1: tuple[float, float, float, float],
    b2: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (
        min(b1[0], b2[0]),
        min(b1[1], b2[1]),
        max(b1[2], b2[2]),
        max(b1[3], b2[3]),
    )


def _is_street(element: Element) -> bool:
    tags = element.get('tags')
    if not tags:
        return False
    if 'highway' in tags:
        return True
    return tags.get('type') in {'route', 'associatedStreet', 'street'} and tags.get(
        'route'
    ) in {'road', 'highway'}


def _get_street_name(result: SearchResult) -> str | None:
    tags = result.element.get('tags')
    if tags:
        if name := tags.get('name'):
            return name.strip()
        if int_name := tags.get('int_name'):
            return int_name.strip()
        for key, val in tags.items():
            if key.startswith('name:') and val:
                return val.strip()
        if ref := tags.get('ref'):
            return ref.strip()
    if result.display_name:
        return result.display_name.split(',')[0].strip()
    return None
