from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from app.config import ID_ASSETS_DIR, ID_VERSION

router = APIRouter(prefix='/static-id')
router.mount(f'/{ID_VERSION}', StaticFiles(directory=ID_ASSETS_DIR), name='static-id')
