from collections.abc import Sequence
from datetime import datetime
from itertools import zip_longest

import cython
import numpy as np
from shapely import GeometryType, MultiPoint, lib

from app.limits import (
    GEO_COORDINATE_PRECISION,
    TRACE_SEGMENT_MAX_AREA,
    TRACE_SEGMENT_MAX_AREA_LENGTH,
    TRACE_SEGMENT_MAX_SIZE,
)
from app.models.db.trace_ import Trace
from app.models.db.trace_segment import TraceSegment
from app.validators.geometry import validate_geometry

_default = object()


class FormatGPX:
    @staticmethod
    def encode_track(segments: Sequence[TraceSegment], trace_: Trace | None = _default) -> dict:
        """
        >>> encode_track([
        ...     TraceSegment(...),
        ...     TraceSegment(...),
        ... ])
        {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        """
        trace_is_default: cython.char = trace_ is _default

        trks: list[dict] = []
        trksegs: list[dict] | None = None
        trkpts: list[dict] | None = None
        last_trace_id: cython.int = -1
        last_track_num: cython.int = -1

        for segment in segments:
            trace = segment.trace if trace_is_default else trace_

            # if trace is available via api, encode full information
            if (trace is not None) and trace.timestamps_via_api:
                trace_id: cython.int = segment.trace_id
                track_num: cython.int = segment.track_num

                # handle trace change
                if last_trace_id != trace_id:
                    trksegs = []
                    trks.append(
                        {
                            'name': trace.name,
                            'desc': trace.description,
                            'url': f'/trace/{trace_id}',
                            'trkseg': trksegs,
                        }
                    )
                    last_trace_id = trace_id
                    last_track_num = -1

                # handle track change
                if last_track_num != track_num:
                    trkpts = []
                    trksegs.append({'trkpt': trkpts})
                    last_track_num = track_num

            # otherwise, encode only coordinates
            else:
                # handle track and track segment change
                if (last_trace_id > -1 or trksegs is None) or (last_track_num > -1 or trkpts is None):
                    trksegs = []
                    trks.append({'trkseg': trksegs})
                    trkpts = []
                    trksegs.append({'trkpt': trkpts})
                    last_trace_id = -1
                    last_track_num = -1

            points: list[tuple[float, float]]
            points = lib.get_coordinates(np.asarray(segment.points, dtype=object), False, False).tolist()
            for point, capture_time, elevation in zip_longest(points, segment.capture_times, segment.elevations):
                data = {'@lon': point[0], '@lat': point[1]}
                if capture_time is not None:
                    data['time'] = capture_time
                if elevation is not None:
                    data['ele'] = elevation
                trkpts.append(data)

        return {'trk': trks}

    @staticmethod
    def decode_tracks(tracks: Sequence[dict], *, track_num_start: cython.int = 0) -> Sequence[TraceSegment]:
        """
        >>> decode_tracks([{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}]}]}])
        [TraceSegment(...)]
        """
        segment_max_area: cython.double = TRACE_SEGMENT_MAX_AREA
        segment_max_area_length: cython.double = TRACE_SEGMENT_MAX_AREA_LENGTH
        segment_max_size: cython.int = TRACE_SEGMENT_MAX_SIZE
        result: list[TraceSegment] = []

        track_num: cython.int
        segment_num: cython.int
        current_minx: cython.double
        current_miny: cython.double
        current_maxx: cython.double
        current_maxy: cython.double
        points: list[tuple[float, float]] = []
        capture_times: list[datetime | None] = []
        elevations: list[float | None] = []

        trk: dict
        trkseg: dict
        trkpt: dict

        for trk in tracks:
            for track_num, trkseg in enumerate(trk.get('trkseg', ()), track_num_start):
                segment_num = 0
                current_minx = 180
                current_miny = 90
                current_maxx = -180
                current_maxy = -90

                for trkpt in trkseg.get('trkpt', ()):
                    lon: float | None = trkpt.get('@lon')
                    lat: float | None = trkpt.get('@lat')
                    if lon is None or lat is None:
                        continue

                    lon_c: cython.double = lon
                    lat_c: cython.double = lat
                    time: str | datetime | None = trkpt.get('time')
                    if time is not None:
                        time = datetime.fromisoformat(time)
                    elevation: str | float | None = trkpt.get('ele')
                    if elevation is not None:
                        elevation = float(elevation)

                    if current_minx > lon_c:
                        current_minx = lon_c
                    if current_miny > lat_c:
                        current_miny = lat_c
                    if current_maxx < lon_c:
                        current_maxx = lon_c
                    if current_maxy < lat_c:
                        current_maxy = lat_c

                    if _should_finish_segment(
                        segment_max_area=segment_max_area,
                        segment_max_area_length=segment_max_area_length,
                        segment_max_size=segment_max_size,
                        minx=current_minx,
                        miny=current_miny,
                        maxx=current_maxx,
                        maxy=current_maxy,
                        points=points,
                    ):
                        _finish_segment(
                            result=result,
                            points=points,
                            capture_times=capture_times,
                            elevations=elevations,
                            track_num=track_num,
                            segment_num=segment_num,
                        )
                        current_minx = lon_c
                        current_miny = lat_c
                        current_maxx = lon_c
                        current_maxy = lat_c
                        segment_num += 1

                    points.append((lon, lat))
                    capture_times.append(time)
                    elevations.append(elevation)

                _finish_segment(
                    result=result,
                    track_num=track_num,
                    segment_num=segment_num,
                    points=points,
                    capture_times=capture_times,
                    elevations=elevations,
                )

            track_num_start = track_num + 1

        return result


@cython.cfunc
def _should_finish_segment(
    *,
    segment_max_area: cython.double,
    segment_max_area_length: cython.double,
    segment_max_size: cython.int,
    minx: cython.double,
    miny: cython.double,
    maxx: cython.double,
    maxy: cython.double,
    points: Sequence[tuple[float, float]],
) -> cython.char:
    """
    Check if the segment should be finished before adding the point.
    """
    width: cython.double = maxx - minx
    height: cython.double = maxy - miny
    return (
        width * height > segment_max_area  # check area
        or width > segment_max_area_length  # check width
        or height > segment_max_area_length  # check height
        or len(points) + 1 >= segment_max_size  # check length
    )


@cython.cfunc
def _finish_segment(
    *,
    result: list[TraceSegment],
    track_num: cython.int,
    segment_num: cython.int,
    points: list[tuple[float, float]],
    capture_times: list[datetime | None],
    elevations: list[float | None],
):
    """
    Finish the segment and add it to the result.
    """
    if not points:
        return

    points_: np.ndarray = lib.points(np.array(points, np.float64).round(GEO_COORDINATE_PRECISION))
    multipoint: MultiPoint = lib.create_collection(points_, GeometryType.MULTIPOINT)
    multipoint = validate_geometry(multipoint)
    capture_times_ = capture_times.copy() if any(v is not None for v in capture_times) else []
    elevations_ = elevations.copy() if any(v is not None for v in elevations) else []

    result.append(
        TraceSegment(
            track_num=track_num,
            segment_num=segment_num,
            points=multipoint,
            capture_times=capture_times_,
            elevations=elevations_,
        )
    )

    points.clear()
    capture_times.clear()
    elevations.clear()
