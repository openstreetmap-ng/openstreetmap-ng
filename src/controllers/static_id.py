from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from starlette.responses import FileResponse

from src.config import ID_ASSETS_DIR

router = APIRouter(prefix='/static-id')

ID_VERSION = 'TODO'  # TODO:


@router.get(f'/{ID_VERSION}/{{path:path}}')
async def get_asset(
    path: Annotated[str, Path(min_length=4)],
) -> FileResponse:
    """
    Serve static assets from iD.
    """

    assets_path = ID_ASSETS_DIR / path

    try:
        absolute_path = await assets_path.resolve(strict=True)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from e

    if not absolute_path.is_relative_to(ID_ASSETS_DIR):
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return FileResponse(absolute_path)
