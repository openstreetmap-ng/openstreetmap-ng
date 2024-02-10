from fastapi import APIRouter
from starlette.staticfiles import StaticFiles

from app.config import RAPID_ASSETS_DIR, RAPID_VERSION

router = APIRouter(prefix='/static-rapid')
router.mount(f'/{RAPID_VERSION}', StaticFiles(directory=RAPID_ASSETS_DIR), name='static-rapid')
