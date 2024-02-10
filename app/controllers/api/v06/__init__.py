from fastapi import APIRouter

import app.controllers.api.v06.changeset as changeset
import app.controllers.api.v06.changeset_comment as changeset_comment
import app.controllers.api.v06.element as element
import app.controllers.api.v06.gpx as gpx
import app.controllers.api.v06.map as map
import app.controllers.api.v06.note as note
import app.controllers.api.v06.trackpoints as trackpoints
import app.controllers.api.v06.user as user
import app.controllers.api.v06.user_pref as user_pref

router = APIRouter(prefix='/0.6')
router.include_router(changeset_comment.router)
router.include_router(changeset.router)
router.include_router(element.router)
router.include_router(gpx.router)
router.include_router(map.router)
router.include_router(note.router)
router.include_router(trackpoints.router)
router.include_router(user_pref.router)
router.include_router(user.router)
