from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from time import perf_counter

import cairosvg
import click
from PIL import Image


@contextmanager
def measure():
    class Result:
        ms: int = 0

    result = Result()
    ts = perf_counter()
    yield result
    tt = perf_counter() - ts
    result.ms = int(tt * 1000)


@click.command()
@click.argument('input', type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('size', '--size', default=128, show_default=True)
@click.option('output_dir', '--output-dir', type=click.Path(exists=True, file_okay=False, path_type=Path))
def svg2raster(input: Path, size: int, output_dir: Path | None) -> None:
    if output_dir is None:
        output_dir = input.parent
    output = output_dir.joinpath(input.stem + '.webp')

    with measure() as cairo_time:
        png_data = cairosvg.svg2png(url=str(input), parent_width=size, parent_height=size)
    with measure() as pillow_time:
        img = Image.open(BytesIO(png_data))
        img.save(output, format='WEBP', quality=80, alpha_quality=80, method=6)

    input_str = click.style(input, fg='cyan')
    output_str = click.style(output, fg='bright_cyan')
    total_ms = cairo_time.ms + pillow_time.ms
    click.echo(f'Converted {input_str} → {output_str} in {total_ms}ms')


if __name__ == '__main__':
    svg2raster()
