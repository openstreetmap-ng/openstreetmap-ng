import cython
import numpy as np
from numpy.typing import NDArray
from rtree.index import Index
from shapely import (
    MultiPolygon,
    Point,
    Polygon,
    box,
    get_coordinates,
    measurement,
    multipolygons,
)

from app.config import (
    CHANGESET_BBOX_LIMIT,
    CHANGESET_NEW_BBOX_MIN_DISTANCE,
    CHANGESET_NEW_BBOX_MIN_RATIO,
)


def extend_changeset_bounds(
    bounds: MultiPolygon | None,
    points: list[Point],
    *,
    CHANGESET_BBOX_LIMIT: cython.ssize_t = CHANGESET_BBOX_LIMIT,
) -> MultiPolygon:
    bboxes: list[list[float]]
    bboxes = measurement.bounds(bounds.geoms).tolist() if bounds is not None else []  # type: ignore
    num_bboxes: cython.ssize_t = len(bboxes)
    num_bounds: cython.ssize_t = num_bboxes
    dirty_mask: list[bool] = [False] * CHANGESET_BBOX_LIMIT

    # create index
    index = Index()
    i: int | None
    for i, bbox in enumerate(bboxes):
        index.insert(i, bbox)

    # process clusters
    for cluster in _cluster_points(points):
        minx, miny = cluster.min(axis=0).tolist()
        maxx, maxy = cluster.max(axis=0).tolist()
        bbox = [minx, miny, maxx, maxy]

        # below the limit, find the intersection, otherwise find the nearest
        i = (
            next(index.intersection(_get_buffer_bbox(bbox), False), None)
            if num_bboxes < CHANGESET_BBOX_LIMIT
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
        i = next(
            (
                idx
                for idx in index.intersection(_get_buffer_bbox(bbox), False)
                if idx != check_i
            ),
            None,
        )
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
    result: list[Polygon] = (
        [
            box(*bboxes[i]) if dirty_mask[i] else poly  # type: ignore
            for i, poly in enumerate(bounds.geoms)
            if not deleted_mask[i]
        ]
        if bounds is not None
        else []
    )
    result.extend(
        box(*bbox)  # type: ignore
        for i, bbox in enumerate(bboxes[num_bounds:], num_bounds)
        if not deleted_mask[i]
    )
    return multipolygons(result)


@cython.cfunc
def _cluster_points(points: list[Point]) -> list[NDArray[np.float64]]:
    num_points: cython.ssize_t = len(points)
    assert num_points > 0, 'Clustering requires at least one point'
    coords = get_coordinates(points)

    if num_points == 1:
        return [coords]

    if num_points <= CHANGESET_BBOX_LIMIT:
        n_clusters = None
        distance_threshold = CHANGESET_NEW_BBOX_MIN_DISTANCE
    else:
        n_clusters = CHANGESET_BBOX_LIMIT
        distance_threshold = None

    labels = _agglomerative_clustering(
        coords, n_clusters=n_clusters, distance_threshold=distance_threshold
    )

    # Sort points by label
    sort_idx = np.argsort(labels)
    sorted_labels = labels[sort_idx]
    sorted_coords = coords[sort_idx]

    # Split the coords at the boundaries
    split_indices = np.unique(sorted_labels, return_index=True)[1][1:]
    return np.split(sorted_coords, split_indices)


@cython.cfunc
def _agglomerative_clustering(
    coords: NDArray[np.float64],
    *,
    n_clusters: int | None,
    distance_threshold: float | None,
) -> NDArray[np.int64]:
    """Agglomerative clustering with single linkage and Chebyshev distance."""
    num_points: cython.ssize_t = len(coords)
    parent = np.arange(num_points)

    if distance_threshold is not None:
        # THRESHOLD-BASED CLUSTERING
        diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]  # (N, N, 2)
        np.abs(diff, out=diff)
        distances = np.max(diff, axis=2)
        del diff

        # Upper triangle pairs with distance <= threshold
        np.less_equal(distances, distance_threshold, out=distances)
        src_idx, dst_idx = np.where(np.triu(distances, k=1))
        del distances

        # Union all close pairs - no sorting needed (single-linkage transitivity)
        for i, j in zip(src_idx, dst_idx, strict=True):
            # Find roots with path halving
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            while parent[j] != j:
                parent[j] = parent[parent[j]]
                j = parent[j]

            # Union if in different clusters
            if i != j:
                parent[j] = i

    else:
        assert n_clusters is not None, (
            'One of n_clusters or distance_threshold must be set'
        )

        # FIXED K-CLUSTERS
        x = coords[:, 0]
        y = coords[:, 1]
        window = min(32, int(num_points - 1))

        # Orders: permutations capture short L∞ neighbors in different orientations.
        # Including x-adjacent pairs makes the candidate graph connected,
        # so we can always reach n_clusters via Kruskal.
        order_x = np.argsort(x)
        order_y = np.argsort(y)
        order_xpy = np.argsort(x + y)
        order_xmy = np.argsort(x - y)
        orders_stacked = np.stack(
            (
                order_x,
                order_x[::-1],
                order_y,
                order_y[::-1],
                order_xpy,
                order_xpy[::-1],
                order_xmy,
                order_xmy[::-1],
            ),
            axis=0,
        )  # (8, N)
        del order_x, order_y, order_xpy, order_xmy

        # Sliding windows: per order, take width (window+1). First column is the
        # source; remaining columns are destinations i+1..i+window.
        orders_win = np.lib.stride_tricks.sliding_window_view(
            orders_stacked, window_shape=window + 1, axis=1
        )  # (8, N-window, window+1)
        orders_win = np.concatenate(
            (orders_win[::2], orders_win[1::2, :window]), axis=1
        )  # (4, N, window+1)
        del orders_stacked

        # Chebyshev distance per (src,dst) pair
        src_ix = orders_win[..., :1]  # (4, N, 1)
        dst_ix = orders_win[..., 1:]  # (4, N, window)
        dx = x[dst_ix]
        dx -= x[src_ix]
        np.abs(dx, out=dx)
        dy = y[dst_ix]
        dy -= y[src_ix]
        np.abs(dy, out=dy)
        np.maximum(dx, dy, out=dx)
        ed = dx.reshape(-1)
        del x, y, src_ix, dst_ix, dx, dy

        # Kruskal: sort edges by weight
        order_e = np.argsort(ed)
        dst_idx = orders_win[..., 1:].reshape(-1)[order_e]
        order_e //= window
        src_idx = orders_win[..., 0].reshape(-1)[order_e]
        del orders_win, ed, order_e

        # Make edges undirected by sorting (src,dst)
        keys = np.minimum(src_idx, dst_idx)
        np.maximum(src_idx, dst_idx, out=dst_idx)
        src_idx[...] = keys

        # Deduplicate edges
        keys *= num_points
        keys += dst_idx
        order = np.argsort(keys)
        keys = keys[order]
        keep_sorted = np.empty(order.size, dtype=bool)
        keep_sorted[0] = True
        np.not_equal(keys[1:], keys[:-1], out=keep_sorted[1:])
        keep = np.empty(order.size, dtype=bool)
        keep[order] = keep_sorted
        src_idx = src_idx[keep]
        dst_idx = dst_idx[keep]
        del keys, order, keep_sorted, keep

        # Union until n_clusters
        for i, j in zip(src_idx, dst_idx, strict=True):
            # Find roots with path halving
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            while parent[j] != j:
                parent[j] = parent[parent[j]]
                j = parent[j]

            # Union if in different clusters
            if i != j:
                parent[j] = i
                num_points -= 1
                if num_points <= n_clusters:
                    break

    del src_idx, dst_idx

    # Vectorized parent-pointer jumping to fully compress paths
    new_parent = parent[parent]
    while not np.array_equal(new_parent, parent):
        parent = new_parent
        new_parent = parent[parent]

    # Relabel to consecutive integers using np.unique's return_inverse
    return np.unique(parent, return_inverse=True)[1]


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
