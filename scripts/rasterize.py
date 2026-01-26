from argparse import ArgumentParser
from contextlib import contextmanager
from io import BytesIO
from multiprocessing.pool import AsyncResult, Pool
from os import utime
from pathlib import Path
from time import perf_counter

import cairosvg
from PIL.Image import open as open_image

from app.lib.image import _save

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


def get_output_path(input: Path, /, *, root: Path):
    output_dir = root.joinpath('_generated', input.parent.relative_to(root))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir.joinpath(input.stem + '.webp')


def rasterize(input: Path, output: Path, /, *, size: int, quality: int):
    png_data = cairosvg.svg2png(url=str(input), output_width=size, output_height=size)
    img = open_image(BytesIO(png_data))
    img_bytes = _save(img, quality, method=6)

    # use lossless encoding if smaller in size
    if quality >= 0:
        img_lossless_bytes = _save(img, -100, method=6)
        if len(img_lossless_bytes) < len(img_bytes):
            img_bytes = img_lossless_bytes

    output.write_bytes(img_bytes)

    # preserve mtime
    mtime = input.stat().st_mtime
    utime(output, (mtime, mtime))


def file(input: list[Path], size: int, quality: int):
    root = Path()
    for i in input:
        output = get_output_path(i, root=root)
        with measure() as time:
            rasterize(i, output, size=size, quality=quality)

        print(
            f'✓ Rasterized SVG to {output} in {time.ms}ms',
        )


def static_img_pipeline(verbose: bool):
    with measure() as time, Pool() as pool:
        jobs: list[AsyncResult[None]] = []

        for root in (Path('app/static/img/element'), Path('app/static/img/browser')):
            for i in root.rglob('*.svg'):
                output = get_output_path(i, root=root)
                if output.is_file() and i.stat().st_mtime <= output.stat().st_mtime:
                    if verbose:
                        print(f'Skipped {output} (already exists)')
                    continue
                jobs.append(
                    pool.apply_async(
                        rasterize, (i, output), {'size': 128, 'quality': 80}
                    )
                )

        root = Path('app/static/img/controls')
        for i in root.rglob('*.svg'):
            output = get_output_path(i, root=root)
            if output.is_file() and i.stat().st_mtime <= output.stat().st_mtime:
                if verbose:
                    print(f'Skipped {output} (already exists)')
                continue
            jobs.append(
                pool.apply_async(rasterize, (i, output), {'size': 80, 'quality': -100})
            )

        pool.close()
        pool.join()
        for job in jobs:
            job.get()

    if jobs:
        print(f'Rasterized {len(jobs)} SVGs in {time.ms}ms')


if __name__ == '__main__':
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)

    parser_file = subparsers.add_parser('file')
    parser_file.set_defaults(func=file)
    parser_file.add_argument('input', nargs='*', type=Path)
    parser_file.add_argument('-s', '--size', type=int, default=DEFAULT_SIZE)
    parser_file.add_argument('-q', '--quality', type=int, default=DEFAULT_QUALITY)

    parser_static_img = subparsers.add_parser('static-img-pipeline')
    parser_static_img.set_defaults(func=static_img_pipeline)
    parser_static_img.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()
    kwargs = vars(args).copy()
    del kwargs['command']
    del kwargs['func']
    args.func(**kwargs)
