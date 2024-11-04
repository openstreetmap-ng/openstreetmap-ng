from typing import TypedDict

# GraphHopper API Documentation:
# https://docs.graphhopper.com/#tag/Routing-API


class GraphHopperInstruction(TypedDict):
    text: str
    distance: float  # in meters
    time: int  # in milliseconds
    interval: list[int]  # indices into points array
    sign: int


class GraphHopperPath(TypedDict):
    points: str  # polyline5 encoded string
    ascend: float  # in meters
    descend: float  # in meters
    instructions: list[GraphHopperInstruction]


class GraphHopperResponse(TypedDict):
    paths: list[GraphHopperPath]
