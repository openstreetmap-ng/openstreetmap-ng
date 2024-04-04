import pytest

from app.format06 import Format06
from app.lib.trace_image import TraceImage

pytestmark = pytest.mark.anyio


async def test_generate(gpx: dict):
    # TODO: fixture?
    trace_points = Format06.decode_tracks(gpx['gpx']['trk'])
    animation, icon = TraceImage.generate(trace_points)

    assert isinstance(animation, bytes)
    assert isinstance(icon, bytes)
    assert len(icon) < len(animation)
