from fastapi import APIRouter

import app.controllers.api.web.avatar as avatar
import app.controllers.api.web.rich_text as rich_text
import app.controllers.api.web.routing as routing
import app.controllers.api.web.unsupported_browser as unsupported_browser
import app.controllers.api.web.user as user

# TODO: partial

router = APIRouter(prefix='/web')
router.include_router(avatar.router)
router.include_router(rich_text.router)
router.include_router(routing.router)
router.include_router(unsupported_browser.router)
router.include_router(user.router)
