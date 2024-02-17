from fastapi import APIRouter

import app.controllers.api as api
import app.controllers.index as index
import app.controllers.shortlink as shortlink
import app.controllers.static_id as static_id
import app.controllers.static_rapid as static_rapid

router = APIRouter()
router.include_router(api.router)
router.include_router(index.router)
router.include_router(shortlink.router)
router.include_router(static_id.router)
router.include_router(static_rapid.router)
