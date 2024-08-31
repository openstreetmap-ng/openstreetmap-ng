import os
from collections.abc import Iterable
from contextlib import contextmanager
from functools import partial
from io import BytesIO
from pathlib import Path
from time import perf_counter

import cairosvg
import click
from PIL import Image

click.secho = partial(click.secho, color=True)
click.echo = partial(click.echo, color=True)


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
@click.argument('input', nargs=-1, type=click.Path(dir_okay=False, path_type=Path))
@click.option('size', '--size', '-s', default=128, show_default=True)
@click.option('quality', '--quality', '-q', default=80, show_default=True)
@click.option('chdir', '--chdir', type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path))
@click.option('force', '--force', '-f', is_flag=True)
def svg2raster(input: Iterable[Path], size: int, quality: int, chdir: Path | None, force: bool) -> None:
    if chdir is not None:
        os.chdir(chdir)

    for i in input:
        output_dir = Path('_generated', i.parent)
        output = output_dir.joinpath(i.stem + '.webp')
        if not output_dir.is_dir():
            output_dir.mkdir(parents=True)

        if not force and output.is_file():
            click.secho(f'Skipped {output} (already exists)', fg='white')
            continue

        with measure() as cairo_time:
            png_data: bytes = cairosvg.svg2png(url=str(i), output_width=size, output_height=size)  # pyright: ignore[reportAssignmentType]
        with measure() as pillow_time:
            img = Image.open(BytesIO(png_data))
            img.save(output, format='WEBP', quality=quality, alpha_quality=quality, method=6)

        check = click.style('✓', fg='bright_green')
        output_str = click.style(output, fg='bright_cyan')
        total_time = click.style(f'{cairo_time.ms + pillow_time.ms}ms', fg='bright_white')
        click.echo(f'{check} Converted SVG to {output_str} in {total_time}')


if __name__ == '__main__':
    svg2raster()
