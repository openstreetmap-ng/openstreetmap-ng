from typing import Annotated

from pydantic import Field

from models.db.oauth_application import OAuthApplication
from models.str import OOB_URIStr, URLStr
from validators.eq import Eq


class OAuth1Application(OAuthApplication):
    application_url: URLStr
    callback_url: OOB_URIStr | None
    support_url: URLStr | None
