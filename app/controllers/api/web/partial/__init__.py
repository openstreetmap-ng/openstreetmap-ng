from fastapi import APIRouter

import app.controllers.api.web.partial.changeset as changeset
import app.controllers.api.web.partial.element as element
import app.controllers.api.web.partial.history as history
import app.controllers.api.web.partial.note as note
import app.controllers.api.web.partial.query as query
import app.controllers.api.web.partial.search as search

router = APIRouter(prefix='/partial')
router.include_router(changeset.router)
router.include_router(element.router)
router.include_router(history.router)
router.include_router(note.router)
router.include_router(query.router)
router.include_router(search.router)
