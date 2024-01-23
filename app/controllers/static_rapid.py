from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from starlette.responses import FileResponse

from app.config import RAPID_ASSETS_DIR, RAPID_VERSION

router = APIRouter(prefix='/static-rapid')


@router.get(f'/{RAPID_VERSION}/{{path:path}}')
async def get_asset(
    path: Annotated[str, Path(min_length=4)],
) -> FileResponse:
    """
    Serve static assets from rapid.
    """

    assets_path = RAPID_ASSETS_DIR / path

    try:
        absolute_path = await assets_path.resolve(strict=True)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from e

    if not absolute_path.is_relative_to(RAPID_ASSETS_DIR):
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return FileResponse(absolute_path)
