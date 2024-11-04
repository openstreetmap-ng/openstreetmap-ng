from typing import TypedDict

# Valhalla API Documentation:
# https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/


class ValhallaLocation(TypedDict):
    lon: float
    lat: float


class ValhallaManeuver(TypedDict):
    type: int
    instruction: str
    time: float  # in seconds
    length: float  # in km
    begin_shape_index: int
    end_shape_index: int


class ValhallaLeg(TypedDict):
    shape: str  # polyline6 encoded string
    maneuvers: list[ValhallaManeuver]
    elevation: list[float]  # in meters


class ValhallaTrip(TypedDict):
    legs: list[ValhallaLeg]


class ValhallaResponse(TypedDict):
    trip: ValhallaTrip
