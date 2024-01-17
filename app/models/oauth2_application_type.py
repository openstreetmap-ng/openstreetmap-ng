from app.models.base_enum import BaseEnum


class OAuth2ApplicationType(BaseEnum):
    public = 'public'
    confidential = 'confidential'
