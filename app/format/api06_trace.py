from collections.abc import Iterable

import cython

from app.lib.auth_context import auth_user
from app.models.db.trace_ import Trace
from app.models.validating.trace_ import TraceValidating


class Trace06Mixin:
    @staticmethod
    def encode_gpx_file(trace: Trace) -> dict:
        """
        >>> encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        """
        return {'gpx_file': _encode_gpx_file(trace)}

    @staticmethod
    def encode_gpx_files(traces: Iterable[Trace]) -> dict:
        """
        >>> encode_gpx_files([
        ...     Trace(...),
        ...     Trace(...),
        ... ])
        {'gpx_file': [{'@id': 1, '@uid': 1234, ...}, {'@id': 2, '@uid': 1234, ...}]}
        """
        return {'gpx_file': tuple(_encode_gpx_file(trace) for trace in traces)}

    @staticmethod
    def decode_gpx_file(gpx_file: dict) -> Trace:
        return Trace(
            **TraceValidating(
                user_id=auth_user(required=True).id,
                name=gpx_file.get('@name'),  # pyright: ignore[reportArgumentType]
                description=gpx_file.get('description'),  # pyright: ignore[reportArgumentType]
                visibility=gpx_file.get('@visibility'),  # pyright: ignore[reportArgumentType]
                size=1,
                tags=gpx_file.get('tag', ()),
            ).__dict__
        )


@cython.cfunc
def _encode_gpx_file(trace: Trace) -> dict:
    """
    >>> _encode_gpx_file(Trace(...))
    {'@id': 1, '@uid': 1234, ...}
    """
    x, y = trace.coords[0].tolist()
    return {
        '@id': trace.id,
        '@uid': trace.user_id,
        '@user': trace.user.display_name,
        '@timestamp': trace.created_at,
        '@name': trace.name,
        '@lon': x,
        '@lat': y,
        '@visibility': trace.visibility,
        '@pending': False,
        'description': trace.description,
        'tag': trace.tags,
    }
