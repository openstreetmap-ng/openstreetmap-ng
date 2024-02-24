from enum import Enum


class TraceVisibility(str, Enum):
    identifiable = 'identifiable'
    public = 'public'
    trackable = 'trackable'
    private = 'private'
