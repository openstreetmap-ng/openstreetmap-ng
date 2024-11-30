from collections.abc import Iterable, Sequence, Sized
from datetime import datetime
from itertools import zip_longest

import cython
import numpy as np
from shapely import Point, lib, multipoints

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
    def encode_track(segments_groups: Iterable[Iterable[TraceSegment]], trace_: Trace | None = _default) -> dict:  # pyright: ignore[reportArgumentType]
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

        for segment in (s for ss in segments_groups for s in ss):
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
                    if trksegs is None:
                        raise AssertionError('Track segments must be set')
                    trkpts = []
                    trksegs.append({'trkpt': trkpts})
                    last_track_num = track_num

            # otherwise, encode only coordinates
            # handle track and track segment change
            elif (last_trace_id > -1 or trksegs is None) or (last_track_num > -1 or trkpts is None):
                trksegs = []
                trks.append({'trkseg': trksegs})
                trkpts = []
                trksegs.append({'trkpt': trkpts})
                last_trace_id = -1
                last_track_num = -1

            points: list[tuple[float, float]]
            points = lib.get_coordinates(np.asarray(segment.points, dtype=np.object_), False, False).tolist()
            capture_times = segment.capture_times
            if capture_times is None:
                capture_times = []
            elevations = segment.elevations
            if elevations is None:
                elevations = []

            if trkpts is None:
                raise AssertionError('Track points must be set')
            for (lon, lat), capture_time, elevation in zip_longest(points, capture_times, elevations):
                data = {'@lon': lon, '@lat': lat}
                if capture_time is not None:
                    data['time'] = capture_time
                if elevation is not None:
                    data['ele'] = elevation
                trkpts.append(data)

        return {'trk': trks}

    @staticmethod
    def decode_tracks(tracks: Iterable[dict], *, track_num_start: cython.int = 0) -> list[TraceSegment]:
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
            track_num = track_num_start
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
                    time_str: str | None = trkpt.get('time')
                    time = datetime.fromisoformat(time_str) if time_str is not None else None
                    elevation_str: str | None = trkpt.get('ele')
                    elevation = float(elevation_str) if elevation_str is not None else None

                    current_minx = min(current_minx, lon_c)
                    current_miny = min(current_miny, lat_c)
                    current_maxx = max(current_maxx, lon_c)
                    current_maxy = max(current_maxy, lat_c)

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
    points: Sized,
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

    points_: Sequence[Point] = lib.points(np.array(points, np.float64).round(GEO_COORDINATE_PRECISION))
    multipoint = validate_geometry(multipoints(points_))
    capture_times_ = capture_times.copy() if any(v is not None for v in capture_times) else None
    elevations_ = elevations.copy() if any(v is not None for v in elevations) else None
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
