from collections.abc import Iterable
from datetime import datetime
from typing import Any, NamedTuple

import cython
import numpy as np
from shapely import MultiLineString, MultiPolygon, Polygon, contains_xy, force_2d, force_3d, get_coordinates, prepare

from app.lib.exceptions_context import raise_for
from app.models.db.trace import Trace, trace_is_timestamps_via_api


class DecodeTracksResult(NamedTuple):
    size: int
    segments: MultiLineString
    capture_times: list[datetime | None] | None


class FormatGPX:
    @staticmethod
    def encode_track(trace: Trace) -> dict:
        """
        >>> encode_track([
        ...     TraceSegment(...),
        ...     TraceSegment(...),
        ... ])
        {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        """
        capture_times = trace['capture_times']
        capture_times_iter = iter(capture_times) if (capture_times is not None) else None
        trkseg: list[dict] = []

        for segment in force_3d(trace['segments']).geoms:
            segment_coords: list[list[float]] = get_coordinates(segment, True).tolist()  # type: ignore
            trkpt: list[dict] = []

            for lon, lat, elevation in segment_coords:
                data: dict[str, Any] = {'@lon': lon, '@lat': lat}
                if elevation:
                    data['ele'] = elevation
                if (
                    capture_times_iter is not None  #
                    and (capture_time := next(capture_times_iter)) is not None
                ):
                    data['time'] = capture_time
                trkpt.append(data)

            trkseg.append({'trkpt': trkpt})

        return {
            'trk': [
                (
                    {
                        'name': trace['name'],
                        'desc': trace['description'],
                        'url': f'/trace/{trace["id"]}',
                        'trkseg': trkseg,
                    }
                    if trace_is_timestamps_via_api(trace)
                    else {
                        'trkseg': trkseg,
                    }
                )
            ]
        }

    @staticmethod
    def encode_tracks_filter(traces: Iterable[Trace], boundary: Polygon | MultiPolygon) -> dict:
        """
        Encode multiple traces as GPX tracks, filtering to only include
        points within the specified boundary geometry.
        """
        # Prepare the boundary for faster contains checks
        prepare(boundary)

        trk: list[dict] = []

        for trace in traces:
            capture_times = trace['capture_times']
            capture_times_arr = np.array(capture_times) if (capture_times is not None) else None
            point_index: cython.int = 0
            trkseg: list[dict] = []

            for segment in force_3d(trace['segments']).geoms:
                segment_coords_arr = get_coordinates(segment, True)
                segment_size: cython.int = len(segment_coords_arr)
                mask = contains_xy(boundary, segment_coords_arr[:, :2])

                # Skip if no points are in boundary
                if not np.any(mask):
                    point_index += segment_size
                    continue

                segment_coords_arr = segment_coords_arr[mask]

                # Add capture times if available
                if capture_times_arr is not None:
                    indices = np.where(mask)[0] + point_index
                    segment_coords_arr = np.column_stack((segment_coords_arr, capture_times_arr[indices]))

                point_index += segment_size
                segment_coords: list[list[Any]] = segment_coords_arr.tolist()  # type: ignore
                trkpt: list[dict] = []

                for t in segment_coords:
                    if capture_times_arr is not None:
                        lon, lat, elevation, capture_time = t
                    else:
                        lon, lat, elevation = t
                        capture_time = None

                    data: dict[str, Any] = {'@lon': lon, '@lat': lat}
                    if elevation:
                        data['ele'] = elevation
                    if capture_time is not None:
                        data['time'] = capture_time
                    trkpt.append(data)

                trkseg.append({'trkpt': trkpt})

            # Add track if it is not empty
            if trkseg:
                trk.append(
                    {
                        'name': trace['name'],
                        'desc': trace['description'],
                        'url': f'/trace/{trace["id"]}',
                        'trkseg': trkseg,
                    }
                    if trace_is_timestamps_via_api(trace)
                    else {
                        'trkseg': trkseg,
                    }
                )

        return {'trk': trk}

    @staticmethod
    def decode_tracks(tracks: Iterable[dict]) -> DecodeTracksResult:
        size: cython.int = 0
        segments: list[list[tuple[float, float, float]]] = []
        capture_times: list[datetime | None] = []
        has_elevation: cython.char = False
        has_capture_times: cython.char = False

        for track in tracks:
            for segment in track.get('trkseg', ()):
                points: list[tuple[float, float, float]] = []  # (lon, lat, elevation)

                for point in segment.get('trkpt', ()):
                    if (lon := point.get('@lon')) is None or (lat := point.get('@lat')) is None:
                        continue

                    # Get elevation if available
                    elevation: float | None = point.get('ele')
                    if elevation is not None:
                        has_elevation = True
                    else:
                        elevation = 0

                    # Get timestamp if available
                    time: datetime | None = point.get('time')
                    if time is not None:
                        has_capture_times = True

                    # Add the point with elevation
                    points.append((lon, lat, elevation))
                    capture_times.append(time)

                # Finish the segment if non-empty
                segment_size: cython.int = len(points)
                if segment_size:
                    if segment_size < 2:
                        raise_for.bad_trace_file('Trace segment is too short or incomplete')

                    size += segment_size
                    segments.append(points)

        if size < 2:
            raise_for.bad_trace_file('Trace is too short or incomplete')

        # Create the MultiLineString
        multilinestring = MultiLineString(segments)

        # Remove Z dimension if no elevation data
        if not has_elevation:
            multilinestring = force_2d(multilinestring)

        return DecodeTracksResult(size, multilinestring, capture_times if has_capture_times else None)
