from app.models.base_enum import BaseEnum


class TraceVisibility(BaseEnum):
    identifiable = 'identifiable'
    public = 'public'
    trackable = 'trackable'
    private = 'private'
