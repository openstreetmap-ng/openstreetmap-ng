from collections.abc import Collection, Sequence

import cython
import numpy as np
from numpy.typing import NDArray
from rtree.index import Index
from shapely import Point, box, get_coordinates, measurement
from sklearn.cluster import AgglomerativeClustering

from app.limits import CHANGESET_BBOX_LIMIT, CHANGESET_NEW_BBOX_MIN_DISTANCE, CHANGESET_NEW_BBOX_MIN_RATIO
from app.models.db.changeset_bounds import ChangesetBounds


def change_bounds(bounds: Collection[ChangesetBounds], points: Sequence[Point]) -> list[ChangesetBounds]:
    bbox_limit: cython.int = CHANGESET_BBOX_LIMIT
    bboxes: list[tuple[float, float, float, float]]
    bboxes = measurement.bounds(tuple(cb.bounds for cb in bounds)).tolist()  # type: ignore
    dirty_mask: list[bool] = [False] * bbox_limit

    # create index
    index = Index()
    i: int | None
    for i, bbox in enumerate(bboxes):
        index.insert(i, bbox)

    # process clusters
    for cluster in _cluster_points(points):
        cluster_ = np.array(cluster, np.float64)
        minx, miny = cluster_.min(axis=0).tolist()
        maxx, maxy = cluster_.max(axis=0).tolist()
        bbox = (minx, miny, maxx, maxy)

        if len(bboxes) < bbox_limit:
            # below the limit, find the intersection
            i = next(index.intersection(_get_buffer_bbox(bbox), False), None)
        else:
            # limit is reached, find the nearest
            i = next(index.nearest(_get_buffer_bbox(bbox), 1, False))

        if i is not None:
            # merge with the existing bbox
            index.delete(i, bboxes[i])
            bbox = bboxes[i] = _union_bbox(bbox, bboxes[i])
            index.insert(i, bbox)
            dirty_mask[i] = True
        else:
            # add new bbox
            i = len(bboxes)
            bboxes.append(bbox)
            index.insert(i, bbox)

    # recheck dirty bboxes
    check_queue: list[int] = list(range(len(bboxes)))
    deleted_mask: list[bool] = [False] * len(bboxes)
    while check_queue:
        check_i = check_queue.pop()
        bbox = bboxes[check_i]
        i = next((idx for idx in index.intersection(_get_buffer_bbox(bbox), False) if idx != check_i), None)
        if i is None:
            continue

        # merge with the existing bbox
        index.delete(check_i, bbox)
        deleted_mask[check_i] = True

        index.delete(i, bboxes[i])
        bbox = bboxes[i] = _union_bbox(bbox, bboxes[i])
        index.insert(i, bbox)
        dirty_mask[i] = True
        check_queue.append(i)

    # combine results
    new_bounds: list[ChangesetBounds] = []
    for i, cb in enumerate(bounds):
        if deleted_mask[i]:
            continue
        if dirty_mask[i]:
            cb.bounds = box(*bboxes[i])
        new_bounds.append(cb)
    new_bounds.extend(
        ChangesetBounds(bounds=box(*bbox))
        for i, bbox in enumerate(bboxes[len(bounds) :], len(bounds))
        if not deleted_mask[i]
    )
    return new_bounds


@cython.cfunc
def _cluster_points(points: Sequence[Point]) -> tuple[list[NDArray[np.float64]], ...]:
    coords = get_coordinates(points)
    if len(coords) == 1:
        return ([coords[0]],)
    if len(coords) <= CHANGESET_BBOX_LIMIT:
        n_clusters = None
        distance_threshold = CHANGESET_NEW_BBOX_MIN_DISTANCE
    else:
        n_clusters = CHANGESET_BBOX_LIMIT
        distance_threshold = None
    clustering = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric='chebyshev',
        linkage='single',
        distance_threshold=distance_threshold,
    )
    clustering.fit(coords)
    clusters: tuple[list[NDArray[np.float64]], ...] = tuple([] for _ in range(clustering.n_clusters_))
    for label, coord in zip(clustering.labels_, coords, strict=True):
        clusters[label].append(coord)
    return clusters


@cython.cfunc
def _get_buffer_bbox(bound: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    new_bbox_min_distance: cython.double = CHANGESET_NEW_BBOX_MIN_DISTANCE
    new_bbox_min_ratio: cython.double = CHANGESET_NEW_BBOX_MIN_RATIO
    minx, miny, maxx, maxy = bound
    distx = (maxx - minx) * new_bbox_min_ratio
    distx = max(distx, new_bbox_min_distance)
    disty = (maxy - miny) * new_bbox_min_ratio
    disty = max(disty, new_bbox_min_distance)
    return minx - distx, miny - disty, maxx + distx, maxy + disty


@cython.cfunc
def _union_bbox(
    b1: tuple[float, float, float, float],
    b2: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    minx = min(b1[0], b2[0])
    miny = min(b1[1], b2[1])
    maxx = max(b1[2], b2[2])
    maxy = max(b1[3], b2[3])
    return minx, miny, maxx, maxy
