import cython
import numpy as np
from numpy.typing import NDArray
from rtree.index import Index
from shapely import MultiPolygon, Point, Polygon, box, get_coordinates, measurement, multipolygons
from sklearn.cluster import AgglomerativeClustering

from app.limits import CHANGESET_BBOX_LIMIT, CHANGESET_NEW_BBOX_MIN_DISTANCE, CHANGESET_NEW_BBOX_MIN_RATIO


def extend_changeset_bounds(bounds: MultiPolygon, points: list[Point]) -> MultiPolygon:
    bbox_limit: cython.Py_ssize_t = CHANGESET_BBOX_LIMIT
    bboxes: list[list[float]]
    bboxes = measurement.bounds(bounds.geoms).tolist()  # type: ignore
    num_bboxes: cython.Py_ssize_t = len(bboxes)
    num_bounds: cython.Py_ssize_t = num_bboxes
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
        bbox = [minx, miny, maxx, maxy]

        # below the limit, find the intersection, otherwise find the nearest
        i = (
            next(index.intersection(_get_buffer_bbox(bbox), False), None)
            if num_bboxes < bbox_limit
            else next(index.nearest(_get_buffer_bbox(bbox), 1, False))
        )

        if i is not None:
            # merge with the existing bbox
            index.delete(i, bboxes[i])
            bbox = bboxes[i] = _union_bbox(bbox, bboxes[i])
            index.insert(i, bbox)
            dirty_mask[i] = True
        else:
            # add new bbox
            bboxes.append(bbox)
            index.insert(num_bboxes, bbox)
            num_bboxes += 1

    # recheck dirty bboxes
    check_queue: list[int] = list(range(num_bboxes))
    deleted_mask: list[bool] = [False] * num_bboxes
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
    result: list[Polygon] = [
        box(*bboxes[i]) if dirty_mask[i] else poly  # type: ignore
        for i, poly in enumerate(bounds.geoms)
        if not deleted_mask[i]
    ]
    result.extend(
        box(*bbox)  # type: ignore
        for i, bbox in enumerate(bboxes[num_bounds:], num_bounds)
        if not deleted_mask[i]
    )
    return multipolygons(result)


@cython.cfunc
def _cluster_points(points: list[Point]) -> list[NDArray[np.float64]]:
    num_points: cython.Py_ssize_t = len(points)
    coords = get_coordinates(points)

    if num_points == 1:
        return [coords]

    if num_points <= CHANGESET_BBOX_LIMIT:
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
    labels = clustering.fit_predict(coords)

    # Sort points by label
    sort_idx = np.argsort(labels)
    sorted_labels = labels[sort_idx]
    sorted_coords = coords[sort_idx]

    # Split the coords at the boundaries
    split_indices = np.unique(sorted_labels, return_index=True)[1][1:]
    return np.split(sorted_coords, split_indices)


@cython.cfunc
def _get_buffer_bbox(bound: list[float]) -> list[float]:
    minx: cython.double = bound[0]
    miny: cython.double = bound[1]
    maxx: cython.double = bound[2]
    maxy: cython.double = bound[3]

    new_bbox_min_distance: cython.double = CHANGESET_NEW_BBOX_MIN_DISTANCE
    new_bbox_min_ratio: cython.double = CHANGESET_NEW_BBOX_MIN_RATIO
    distx = (maxx - minx) * new_bbox_min_ratio
    distx = max(distx, new_bbox_min_distance)
    disty = (maxy - miny) * new_bbox_min_ratio
    disty = max(disty, new_bbox_min_distance)

    return [
        minx - distx,
        miny - disty,
        maxx + distx,
        maxy + disty,
    ]


@cython.cfunc
def _union_bbox(b1: list[float], b2: list[float]) -> list[float]:
    return [
        min(b1[0], b2[0]),
        min(b1[1], b2[1]),
        max(b1[2], b2[2]),
        max(b1[3], b2[3]),
    ]
