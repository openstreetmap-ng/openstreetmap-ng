from datetime import datetime

from pydantic import NonNegativeInt

from models.db.base import Base
from models.geometry import PointGeometry


class TracePointValidating(Base.Validating):
    track_idx: NonNegativeInt
    captured_at: datetime
    point: PointGeometry
    elevation: float | None
