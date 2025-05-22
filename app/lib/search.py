import logging
from dataclasses import dataclass

import cython
import numpy as np
from shapely import MultiPolygon, Point, Polygon, STRtree

from app.config import (
    SEARCH_LOCAL_AREA_LIMIT,
    SEARCH_LOCAL_MAX_ITERATIONS,
    SEARCH_LOCAL_RATIO,
)
from app.lib.feature_icon import FeatureIcon
from app.lib.geo_utils import parse_bbox
from app.models.db.element import Element
from app.models.element import TypedElementId
from speedup import split_typed_element_ids

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
        bbox: str,
        *,
        local_only: bool = False,
        local_max_iterations: int | None = None,
    ) -> list[tuple[str, Polygon | MultiPolygon] | tuple[None, None]]:
        """
        Get search bounds from a bbox string.

        Returns a list of (leaflet, shapely) bounds.
        """
        search_local_area_limit: cython.double = SEARCH_LOCAL_AREA_LIMIT
        search_local_max_iterations: cython.int = (
            local_max_iterations
            if local_max_iterations is not None
            else SEARCH_LOCAL_MAX_ITERATIONS
        )

        parts = bbox.strip().split(',', 3)
        minx: cython.double = float(parts[0])
        miny: cython.double = float(parts[1])
        maxx: cython.double = float(parts[2])
        maxy: cython.double = float(parts[3])

        bbox_width = maxx - minx
        bbox_width_2 = bbox_width / 2
        bbox_height = maxy - miny
        bbox_height_2 = bbox_height / 2
        bbox_area = bbox_width * bbox_height

        bbox_center_x = minx + bbox_width_2
        bbox_center_y = miny + bbox_height_2

        local_iterations: cython.int = (
            1 if local_only else int(ceil(log2(search_local_area_limit / bbox_area)))  # noqa: RUF046
        )
        local_iterations = min(local_iterations, search_local_max_iterations)

        logging.debug(
            'Searching area of %d with %d local iterations', bbox_area, local_iterations
        )
        result: list[tuple[str, Polygon | MultiPolygon] | tuple[None, None]]
        result = [None] * local_iterations  # type: ignore

        i: cython.Py_ssize_t
        for i in range(local_iterations):
            bounds_width_2 = bbox_width_2 * (2**i)
            bounds_height_2 = bbox_height_2 * (2**i)
            bounds_minx = bbox_center_x - bounds_width_2
            bounds_miny = bbox_center_y - bounds_height_2
            bounds_maxx = bbox_center_x + bounds_width_2
            bounds_maxy = bbox_center_y + bounds_height_2
            leaflet_bounds = f'{bounds_minx:.7f},{bounds_miny:.7f},{bounds_maxx:.7f},{bounds_maxy:.7f}'
            shapely_bounds = parse_bbox(leaflet_bounds)
            result[i] = (leaflet_bounds, shapely_bounds)

        if not local_only:
            # append global search bounds
            result.append((None, None))

        return result

    @staticmethod
    def best_results_index(task_results: list[list[SearchResult]]) -> int:
        """Determine the best results index."""
        # local_only mode
        if len(task_results) == 1:
            return 0

        if _should_use_global_search(task_results):
            # global search
            logging.debug('Search performed using global mode')
            return -1

        logging.debug('Search performed using local mode')
        max_local_results: cython.Py_ssize_t = len(task_results[-2])
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
    ) -> None:
        """Improve accuracy of points by analyzing relations members."""
        for result, type_id in zip(
            results,
            split_typed_element_ids([result.element['typed_id'] for result in results]),
            strict=True,
        ):
            if type_id[0] != 'relation':
                continue

            element = result.element
            members = element['members']
            assert members is not None, 'Relation members must be set'
            members_roles = element['members_roles']
            assert members_roles is not None, 'Relation members roles must be set'

            success: cython.bint = False
            for member, member_type_id, role in zip(
                members,
                split_typed_element_ids(members),
                members_roles,
                strict=True,
            ):
                if member_type_id[0] != 'node' or (success and role != 'admin_centre'):
                    continue

                point = members_map[member]['point']
                if point is not None:
                    result.point = point
                    success = True

    @staticmethod
    def remove_overlapping_points(results: list[SearchResult]) -> None:
        """Remove overlapping points, preserving most important results."""
        relations = [
            result
            for result, type_id in zip(
                results,
                split_typed_element_ids([
                    result.element['typed_id'] for result in results
                ]),
                strict=True,
            )
            if type_id[0] == 'relation'
        ]
        if len(relations) <= 1:
            return

        geoms = [result.point for result in relations]
        tree = STRtree(geoms)

        nearby_all = tree.query(geoms, 'dwithin', 0.001).T
        nearby_all = np.unique(nearby_all, axis=0)
        nearby_all = nearby_all[nearby_all[:, 0] < nearby_all[:, 1]]
        nearby_all = np.sort(nearby_all, axis=1)

        for i1, i2 in nearby_all.tolist():  # type: ignore
            if relations[i1].point is not None:
                relations[i2].point = None

    @staticmethod
    def deduplicate_similar_results(results: list[SearchResult]) -> list[SearchResult]:
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

        num_geoms: cython.Py_ssize_t = len(geoms)
        if num_geoms <= 1:
            return dedup1

        # Deduplicate by location and name
        tree = STRtree(geoms)

        nearby_all = tree.query(geoms, 'dwithin', 0.001).T
        nearby_all = np.unique(nearby_all, axis=0)
        nearby_all = nearby_all[nearby_all[:, 0] < nearby_all[:, 1]]
        nearby_all = np.sort(nearby_all, axis=1)

        mask = [True] * num_geoms
        for i1, i2 in nearby_all.tolist():  # type: ignore
            if not mask[i1]:
                continue
            name1 = dedup1[i1].display_name
            name2 = dedup1[i2].display_name
            if name1 == name2:
                mask[i2] = False

        return [result for result, is_mask in zip(dedup1, mask, strict=True) if is_mask]


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
