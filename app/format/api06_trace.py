from collections.abc import Sequence

import cython

from app.lib.auth_context import auth_user
from app.models.db.trace_ import Trace
from app.validators.trace_ import TraceValidating


class Trace06Mixin:
    @staticmethod
    def encode_gpx_file(trace: Trace) -> dict:
        """
        >>> encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        """
        return {'gpx_file': _encode_gpx_file(trace)}

    @staticmethod
    def encode_gpx_files(traces: Sequence[Trace]) -> dict:
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
            **dict(
                TraceValidating(
                    user_id=auth_user().id,
                    name=gpx_file.get('@name'),
                    description=gpx_file.get('description'),
                    visibility=gpx_file.get('@visibility'),
                    size=1,
                    tags=gpx_file.get('tag', ()),
                )
            )
        )


@cython.cfunc
def _encode_gpx_file(trace: Trace) -> dict:
    """
    >>> _encode_gpx_file(Trace(...))
    {'@id': 1, '@uid': 1234, ...}
    """
    return {
        '@id': trace.id,
        '@uid': trace.user_id,
        '@user': trace.user.display_name,
        '@timestamp': trace.created_at,
        '@name': trace.name,
        '@lon': trace.coords[0],
        '@lat': trace.coords[1],
        '@visibility': trace.visibility,
        '@pending': False,
        'description': trace.description,
        'tag': trace.tags,
    }
