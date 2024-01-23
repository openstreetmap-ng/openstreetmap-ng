from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from starlette.responses import FileResponse

from app.config import LOCALE_DIR, LOCALE_FRONTEND_VERSION
from app.limits import LANGUAGE_CODE_MAX_LENGTH

router = APIRouter(prefix='/static-locale')

_locale_frontend_dir = LOCALE_DIR / 'frontend'


@router.get(f'/{LOCALE_FRONTEND_VERSION}/{{locale}}.json')
async def get_locale(
    locale: Annotated[str, Path(min_length=2, max_length=LANGUAGE_CODE_MAX_LENGTH)],
) -> FileResponse:
    """
    Serve static locale assets for the frontend.
    """

    locale_path = _locale_frontend_dir / f'{locale}.json'

    try:
        absolute_path = await locale_path.resolve(strict=True)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from e

    if not absolute_path.is_relative_to(_locale_frontend_dir):
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return FileResponse(absolute_path)
