from typing import Annotated

from pydantic import Field

from models.db.oauth_application import OAuthApplication
from models.str import NonEmptyStr, URIStr
from validators.eq import Eq


class OAuth2Application(OAuthApplication):
    type: NonEmptyStr  # TODO: public, confidential
    redirect_uris: list[URIStr]
