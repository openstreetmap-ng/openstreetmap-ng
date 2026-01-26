import cython
import numpy as np
from numpy.typing import NDArray
from shapely import (
    MultiPolygon,
    Point,
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

_BBox = list[float]

_FIXED_K_MAX_CANDIDATE_EDGES = 5_000_000


def extend_changeset_bounds(
    bounds: MultiPolygon | None,
    points: list[Point],
    *,
    CHANGESET_BBOX_LIMIT: cython.size_t = CHANGESET_BBOX_LIMIT,
):
    bboxes: list[_BBox]
    bboxes = measurement.bounds(bounds.geoms).tolist() if bounds is not None else []  # type: ignore
    num_bboxes: cython.size_t = len(bboxes)
    num_bounds: cython.size_t = num_bboxes
    dirty_mask = [False] * CHANGESET_BBOX_LIMIT

    # process clusters
    for bbox in _cluster_point_bboxes(points):
        buffer_bbox = _get_buffer_bbox(bbox)

        if num_bboxes < CHANGESET_BBOX_LIMIT:
            for j, existing in enumerate(bboxes):
                if _bbox_intersects(buffer_bbox, existing):
                    i = j
                    break
            else:
                i = None
        else:
            best_d2: cython.double = float('inf')
            best_i = None
            for j, existing in enumerate(bboxes):
                d2 = _bbox_distance2(buffer_bbox, existing)
                if d2 < best_d2:
                    best_d2 = d2
                    best_i = j
            i = best_i

        if i is not None:
            # merge with the existing bbox
            _merge_bbox(bboxes, dirty_mask, bbox, i)
        else:
            # add new bbox
            bboxes.append(bbox)
            num_bboxes += 1

    # recheck dirty bboxes
    check_queue = list(range(num_bboxes))
    deleted_mask = [False] * num_bboxes
    while check_queue:
        check_i = check_queue.pop()
        bbox = bboxes[check_i]

        buffer_bbox = _get_buffer_bbox(bbox)
        for j, existing in enumerate(bboxes):
            if j == check_i or deleted_mask[j]:
                continue
            if _bbox_intersects(buffer_bbox, existing):
                i = j
                break
        else:
            continue

        # delete bbox at check_i
        deleted_mask[check_i] = True

        # merge bbox into i (if it expands it)
        if _merge_bbox(bboxes, dirty_mask, bbox, i):
            check_queue.append(i)

    # combine results
    result = (
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
def _merge_bbox(
    bboxes: list[_BBox],
    dirty_mask: list[bool],
    bbox: _BBox,
    i: int,
):
    existing = bboxes[i]
    merged = _union_bbox(bbox, existing)
    if merged == existing:
        return False

    bboxes[i] = merged
    dirty_mask[i] = True
    return True


@cython.cfunc
def _cluster_point_bboxes(points: list[Point]) -> list[_BBox]:
    num_points = len(points)
    assert num_points > 0, 'Clustering requires at least one point'
    coords = get_coordinates(points)

    if num_points == 1:
        x, y = coords[0]
        return [[x, y, x, y]]

    if num_points <= CHANGESET_BBOX_LIMIT:
        labels = _agglomerative_clustering(
            coords,
            num_clusters=None,
            distance_threshold=CHANGESET_NEW_BBOX_MIN_DISTANCE,
        )
        return _labels_to_bboxes(coords, labels)

    if num_points <= (_FIXED_K_MAX_CANDIDATE_EDGES // 4):
        labels = _agglomerative_clustering(
            coords,
            num_clusters=CHANGESET_BBOX_LIMIT,
            distance_threshold=None,
        )
        return _labels_to_bboxes(coords, labels)

    return _k_center_bboxes(coords, num_clusters=CHANGESET_BBOX_LIMIT)


@cython.cfunc
def _labels_to_bboxes(
    coords: NDArray[np.float64], labels: NDArray[np.int64]
) -> list[_BBox]:
    return _reduce_labels_to_bboxes_xy(
        x=coords[:, 0],
        y=coords[:, 1],
        labels=labels,
        num_clusters=int(labels.max()) + 1,
    ).tolist()


@cython.cfunc
def _reduce_labels_to_bboxes_xy(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    labels: NDArray[np.integer],
    num_clusters: int,
):
    minx = np.full(num_clusters, np.inf, dtype=np.float64)
    miny = np.full(num_clusters, np.inf, dtype=np.float64)
    maxx = np.full(num_clusters, -np.inf, dtype=np.float64)
    maxy = np.full(num_clusters, -np.inf, dtype=np.float64)

    np.minimum.at(minx, labels, x)
    np.minimum.at(miny, labels, y)
    np.maximum.at(maxx, labels, x)
    np.maximum.at(maxy, labels, y)

    return np.stack((minx, miny, maxx, maxy), axis=1)


@cython.cfunc
def _k_center_bboxes(coords: NDArray[np.float64], *, num_clusters: int) -> list[_BBox]:
    x = coords[:, 0]
    y = coords[:, 1]
    labels = np.zeros(len(coords), dtype=np.int8)

    first = np.argmin(x)
    dist = np.abs(x - x[first])
    np.maximum(dist, np.abs(y - y[first]), out=dist)

    for n in range(1, num_clusters):
        next_center = np.argmax(dist)
        dx = np.abs(x - x[next_center])
        np.maximum(dx, np.abs(y - y[next_center]), out=dx)

        improved = dx < dist
        labels[improved] = n
        dist[improved] = dx[improved]

    counts = np.bincount(labels, minlength=num_clusters)
    keep = counts > 0
    return _reduce_labels_to_bboxes_xy(x, y, labels, num_clusters)[keep].tolist()


@cython.cfunc
def _agglomerative_clustering(
    coords: NDArray[np.float64],
    *,
    num_clusters: int | None,
    distance_threshold: float | None,
) -> NDArray[np.int64]:
    """Agglomerative clustering with single linkage and Chebyshev distance."""
    num_points: cython.size_t = len(coords)
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
        assert num_clusters is not None, (
            'One of n_clusters or distance_threshold must be set'
        )

        # FIXED K-CLUSTERS
        x = coords[:, 0]
        y = coords[:, 1]
        window: cython.size_t = min(32, num_points - 1)
        window_budget: cython.size_t = _FIXED_K_MAX_CANDIDATE_EDGES // (4 * num_points)
        window = min(window, max(1, window_budget))

        # Orders: permutations capture short L∞ neighbors in different orientations.
        # Including x-adjacent pairs makes the candidate graph connected,
        # so we can always reach n_clusters via Kruskal.
        orders = (
            np.argsort(x),
            np.argsort(y),
            np.argsort(x + y),
            np.argsort(x - y),
        )

        edges_per_order = window * num_points - (window * (window + 1) // 2)
        num_edges = edges_per_order * len(orders)
        src_idx = np.empty(num_edges, dtype=np.int64)
        dst_idx = np.empty(num_edges, dtype=np.int64)

        pos = 0
        order: NDArray[np.int64]
        d: int
        for order in orders:
            for d in range(1, window + 1):
                m = num_points - d
                src_idx[pos : pos + m] = order[:m]
                dst_idx[pos : pos + m] = order[d:]
                pos += m

        dx = x[dst_idx] - x[src_idx]
        np.abs(dx, out=dx)
        dy = y[dst_idx] - y[src_idx]
        np.abs(dy, out=dy)
        np.maximum(dx, dy, out=dx)

        order_e = np.argsort(dx)
        src_idx = src_idx[order_e]
        dst_idx = dst_idx[order_e]
        del x, y, dx, dy, order_e

        # Make edges undirected by sorting (src,dst)
        keys = np.minimum(src_idx, dst_idx)
        np.maximum(src_idx, dst_idx, out=dst_idx)
        src_idx[...] = keys

        # Deduplicate edges
        keys *= num_points
        keys += dst_idx
        order = np.argsort(keys)
        keys = keys[order]
        keep_sorted = np.empty(len(order), dtype=bool)
        keep_sorted[0] = True
        np.not_equal(keys[1:], keys[:-1], out=keep_sorted[1:])
        keep = np.empty(len(order), dtype=bool)
        keep[order] = keep_sorted
        src_idx = src_idx[keep]
        dst_idx = dst_idx[keep]
        del keys, order, keep_sorted, keep

        # Union until n_clusters
        num_components: cython.size_t = num_points
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
                num_components -= 1
                if num_components <= num_clusters:
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
def _get_buffer_bbox(bound: _BBox, /) -> _BBox:
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
def _bbox_intersects(a: _BBox, b: _BBox, /):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


@cython.cfunc
def _bbox_distance2(a: _BBox, b: _BBox, /):
    a0: cython.double
    a1: cython.double
    a2: cython.double
    a3: cython.double
    b0: cython.double
    b1: cython.double
    b2: cython.double
    b3: cython.double

    dx: cython.double
    dy: cython.double

    if (b2 := b[2]) < (a0 := a[0]):
        dx = a0 - b2
    elif (a2 := a[2]) < (b0 := b[0]):
        dx = b0 - a2
    else:
        dx = 0

    if (b3 := b[3]) < (a1 := a[1]):
        dy = a1 - b3
    elif (a3 := a[3]) < (b1 := b[1]):
        dy = b1 - a3
    else:
        dy = 0

    return dx * dx + dy * dy


@cython.cfunc
def _union_bbox(b1: _BBox, b2: _BBox, /) -> _BBox:
    return [
        min(b1[0], b2[0]),
        min(b1[1], b2[1]),
        max(b1[2], b2[2]),
        max(b1[3], b2[3]),
    ]
