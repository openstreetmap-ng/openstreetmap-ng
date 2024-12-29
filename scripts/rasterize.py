import os
from collections.abc import Iterable
from contextlib import contextmanager
from functools import partial
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


def get_output_path(input: Path, /, *, root: Path) -> Path:
    output_dir = Path(root, '_generated', input.parent.relative_to(root))
    if not output_dir.is_dir():
        output_dir.mkdir(parents=True)
    return output_dir.joinpath(input.stem + '.webp')


def rasterize(input: Path, output: Path, /, *, size: int, quality: int) -> None:
    import cairosvg
    import cv2
    import numpy as np

    png_data: bytes = cairosvg.svg2png(url=str(input), output_width=size, output_height=size)
    img = cv2.imdecode(np.frombuffer(png_data, np.uint8), cv2.IMREAD_UNCHANGED)
    _, img = cv2.imencode(output.suffix, img, (cv2.IMWRITE_WEBP_QUALITY, quality))

    # use lossless encoding if smaller in size
    if quality <= 100:
        _, img_lossless = cv2.imencode(output.suffix, img, (cv2.IMWRITE_WEBP_QUALITY, 101))
        if img_lossless.size < img.size:
            img = img_lossless

    img.tofile(output)

    # preserve mtime
    mtime = input.stat().st_mtime
    os.utime(output, (mtime, mtime))


@cli.command()
@click.argument('input', nargs=-1, type=click.Path(dir_okay=False, path_type=Path))
@click.option('size', '--size', '-s', default=DEFAULT_SIZE, show_default=True)
@click.option('quality', '--quality', '-q', default=DEFAULT_QUALITY, show_default=True)
def file(input: Iterable[Path], size: int, quality: int) -> None:
    root = Path()
    for i in input:
        output = get_output_path(i, root=root)
        with measure() as time:
            rasterize(i, output, size=size, quality=quality)

        check = click.style('✓', fg='bright_green')
        output_str = click.style(output, fg='bright_cyan')
        total_time = click.style(f'{time.ms}ms', fg='bright_white')
        click.echo(f'{check} Rasterized SVG to {output_str} in {total_time}')


@cli.command('static-img-pipeline')
@click.option('verbose', '--verbose', '-v', is_flag=True)
def static_img_pipeline(verbose: bool) -> None:
    with measure() as time, Pool() as pool:
        success_counter = 0

        root = Path('app/static/img/element')
        for i in root.rglob('*.svg'):
            output = get_output_path(i, root=root)
            if output.is_file() and i.stat().st_mtime <= output.stat().st_mtime:
                if verbose:
                    click.secho(f'Skipped {output} (already exists)', fg='white')
                continue
            pool.apply_async(partial(rasterize, i, output, size=128, quality=80))
            success_counter += 1

        root = Path('app/static/img/leaflet')
        for i in root.rglob('*.svg'):
            output = get_output_path(i, root=root)
            if output.is_file() and i.stat().st_mtime <= output.stat().st_mtime:
                if verbose:
                    click.secho(f'Skipped {output} (already exists)', fg='white')
                continue
            pool.apply_async(partial(rasterize, i, output, size=80, quality=101))
            success_counter += 1

        pool.close()
        pool.join()

    if success_counter > 0:
        output_str = click.style(str(success_counter), fg='bright_cyan')
        total_time = click.style(f'{time.ms}ms', fg='bright_white', bold=True)
        click.echo(f'Rasterized {output_str} SVGs in {total_time}')


if __name__ == '__main__':
    cli()
