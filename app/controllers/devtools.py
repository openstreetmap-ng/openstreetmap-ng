from fastapi import APIRouter, Response
from starlette import status

from app.config import ENV

router = APIRouter()


if ENV == 'dev':

    @router.get('/.well-known/appspecific/com.chrome.devtools.json')
    async def chrome_devtools_json():
        return Response(None, status.HTTP_204_NO_CONTENT)
