import os
from collections.abc import Iterable
from contextlib import contextmanager
from functools import partial
from io import BytesIO
from multiprocessing.pool import Pool
from pathlib import Path
from time import perf_counter

import click

cli = click.Group()

DEFAULT_SIZE = 128
DEFAULT_QUALITY = 80


@contextmanager
def measure():
    class Result:
        ms: int = 0

    result = Result()
    ts = perf_counter()
    yield result
    tt = perf_counter() - ts
    result.ms = int(tt * 1000)


def get_output_path(input: Path, /) -> Path:
    output_dir = Path('_generated', input.parent)
    output = output_dir.joinpath(input.stem + '.webp')
    if not output_dir.is_dir():
        output_dir.mkdir(parents=True)
    return output


def rasterize(input: Path, output: Path, /, *, size: int, quality: int) -> None:
    import cairosvg
    from PIL import Image

    with measure() as time:
        png_data: bytes = cairosvg.svg2png(url=str(input), output_width=size, output_height=size)  # pyright: ignore[reportAssignmentType]
        img = Image.open(BytesIO(png_data))
        img.save(output, format='WEBP', quality=quality, alpha_quality=quality, method=6)

        # preserve mtime
        mtime = input.stat().st_mtime
        os.utime(output, (mtime, mtime))

    check = click.style('✓', fg='bright_green')
    output_str = click.style(output, fg='bright_cyan')
    total_time = click.style(f'{time.ms}ms', fg='bright_white')
    click.echo(f'{check} Rasterized SVG to {output_str} in {total_time}')


@cli.command()
@click.argument('input', nargs=-1, type=click.Path(dir_okay=False, path_type=Path))
@click.option('size', '--size', '-s', default=DEFAULT_SIZE, show_default=True)
@click.option('quality', '--quality', '-q', default=DEFAULT_QUALITY, show_default=True)
def file(input: Iterable[Path], size: int, quality: int) -> None:
    for i in input:
        output = get_output_path(i)
        rasterize(i, output, size=size, quality=quality)


@cli.command('static-img-pipeline')
@click.option('verbose', '--verbose', '-v', is_flag=True)
def static_img_pipeline(verbose: bool) -> None:
    os.chdir('app/static/img/element')
    with Pool() as pool:
        for i in Path().rglob('*.svg'):
            output = get_output_path(i)
            if output.is_file() and i.stat().st_mtime <= output.stat().st_mtime:
                if verbose:
                    click.secho(f'Skipped {output} (already exists)', fg='white')
                continue
            pool.apply_async(partial(rasterize, i, output, size=128, quality=80))
        pool.close()
        pool.join()


if __name__ == '__main__':
    cli()
