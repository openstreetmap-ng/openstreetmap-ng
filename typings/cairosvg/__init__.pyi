from io import IOBase
from typing import overload

# https://cairosvg.org/documentation/

@overload
def svg2png(
    *,
    url: str,
    parent_width: int = ...,
    parent_height: int = ...,
    dpi: int = ...,
    scale: float = ...,
    unsafe: bool = ...,
    output_width: int = ...,
    output_height: int = ...,
) -> bytes: ...
@overload
def svg2png(
    *,
    file_obj: IOBase,
    parent_width: int = ...,
    parent_height: int = ...,
    dpi: int = ...,
    scale: float = ...,
    unsafe: bool = ...,
    output_width: int = ...,
    output_height: int = ...,
) -> bytes: ...
@overload
def svg2png(
    *,
    bytestring: bytes,
    parent_width: int = ...,
    parent_height: int = ...,
    dpi: int = ...,
    scale: float = ...,
    unsafe: bool = ...,
    output_width: int = ...,
    output_height: int = ...,
) -> bytes: ...
