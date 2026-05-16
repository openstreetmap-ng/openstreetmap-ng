from typing import override

from connectrpc.request import RequestContext
from starlette.exceptions import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from app.lib.auth.context import require_web_user
from app.models.db.oauth2_application import OAuth2Uri
from app.models.db.oauth2_token import (
    OAuth2CodeChallengeMethod,
    OAuth2ResponseMode,
    OAuth2TokenOOB,
)
from app.models.proto.oauth2_authorize_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.oauth2_authorize_pb2 import (
    AuthorizeRequest,
    AuthorizeResponse,
)
from app.models.proto.oauth2_authorize_pb2 import (
    CodeChallengeMethod as ProtoCodeChallengeMethod,
)
from app.models.proto.oauth2_authorize_pb2 import (
    ResponseMode as ProtoResponseMode,
)
from app.models.scope import scope_from_str
from app.models.types import ClientId
from app.services.oauth2_token_service import OAuth2TokenService
from app.utils import extend_query_params


class _Service(Service):
    @override
    async def authorize(self, request: AuthorizeRequest, ctx: RequestContext):
        require_web_user()

        response_mode: OAuth2ResponseMode = (
            ProtoResponseMode.Name(request.response_mode)
            if request.HasField('response_mode')
            else 'query'
        )
        code_challenge_method: OAuth2CodeChallengeMethod | None = None
        code_challenge: str | None = None
        if request.HasField('pkce'):
            code_challenge_method = ProtoCodeChallengeMethod.Name(request.pkce.method)
            code_challenge = request.pkce.challenge

        auth_result = await OAuth2TokenService.authorize(
            init=False,
            client_id=ClientId(request.client_id),
            redirect_uri=OAuth2Uri(request.redirect_uri),
            scopes=scope_from_str(request.scope),
            code_challenge_method=code_challenge_method,
            code_challenge=code_challenge,
            state=request.state if request.HasField('state') else None,
        )

        if isinstance(auth_result, OAuth2TokenOOB):
            return AuthorizeResponse(oob_code=str(auth_result))

        # Sanity check: the OAuth2Application case is `init=True` only.
        assert 'redirect_uris' not in auth_result, (
            'authorize(init=False) must not return an OAuth2Application'
        )

        if response_mode in {'query', 'fragment'}:
            final_uri = extend_query_params(
                request.redirect_uri,
                auth_result,
                fragment=response_mode == 'fragment',
            )
            return AuthorizeResponse(redirect_uri=final_uri)

        if response_mode == 'form_post':
            form_post = AuthorizeResponse.FormPost(action_url=request.redirect_uri)
            for k, v in auth_result.items():
                form_post.fields[k] = str(v)
            return AuthorizeResponse(form_post=form_post)

        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            f'Unsupported response mode {response_mode!r}',
        )


service = _Service()
asgi_app_cls = ServiceASGIApplication
