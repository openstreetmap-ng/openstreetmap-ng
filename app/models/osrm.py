from typing import NotRequired, TypedDict

# OSRM API Documentation:
# https://project-osrm.org/docs/v5.24.0/api/#route-service


class OSRMStepManeuver(TypedDict):
    type: str
    modifier: NotRequired[str]
    exit: NotRequired[int]


class OSRMStep(TypedDict):
    distance: float  # in meters
    duration: float  # in seconds
    geometry: str  # polyline6 encoded string
    name: str
    ref: NotRequired[str]
    destinations: NotRequired[str]
    exits: NotRequired[str]
    maneuver: OSRMStepManeuver


class OSRMLeg(TypedDict):
    steps: list[OSRMStep]


class OSRMRoute(TypedDict):
    legs: list[OSRMLeg]


class OSRMResponse(TypedDict):
    routes: list[OSRMRoute]
