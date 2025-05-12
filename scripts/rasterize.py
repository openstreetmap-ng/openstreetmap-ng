from argparse import ArgumentParser
from contextlib import contextmanager
from functools import partial
from multiprocessing.pool import Pool
from os import utime
from pathlib import Path
from time import perf_counter

import cairosvg
import cv2
import numpy as np

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
    output_dir = root.joinpath('_generated', input.parent.relative_to(root))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir.joinpath(input.stem + '.webp')


def rasterize(input: Path, output: Path, /, *, size: int, quality: int) -> None:
    png_data = cairosvg.svg2png(url=str(input), output_width=size, output_height=size)
    img = cv2.imdecode(np.frombuffer(png_data, np.uint8), cv2.IMREAD_UNCHANGED)
    _, img = cv2.imencode(output.suffix, img, (cv2.IMWRITE_WEBP_QUALITY, quality))

    # use lossless encoding if smaller in size
    if quality <= 100:
        _, img_lossless = cv2.imencode(
            output.suffix, img, (cv2.IMWRITE_WEBP_QUALITY, 101)
        )
        if img_lossless.size < img.size:
            img = img_lossless

    img.tofile(output)

    # preserve mtime
    mtime = input.stat().st_mtime
    utime(output, (mtime, mtime))


def file(input: list[Path], size: int, quality: int) -> None:
    root = Path()
    for i in input:
        output = get_output_path(i, root=root)
        with measure() as time:
            rasterize(i, output, size=size, quality=quality)

        print(
            f'✓ Rasterized SVG to {output} in {time.ms}ms',
        )


def static_img_pipeline(verbose: bool) -> None:
    with measure() as time, Pool() as pool:
        success_counter = 0

        root = Path('app/static/img/element')
        for i in root.rglob('*.svg'):
            output = get_output_path(i, root=root)
            if output.is_file() and i.stat().st_mtime <= output.stat().st_mtime:
                if verbose:
                    print(f'Skipped {output} (already exists)')
                continue
            pool.apply_async(partial(rasterize, i, output, size=128, quality=80))
            success_counter += 1

        root = Path('app/static/img/leaflet')
        for i in root.rglob('*.svg'):
            output = get_output_path(i, root=root)
            if output.is_file() and i.stat().st_mtime <= output.stat().st_mtime:
                if verbose:
                    print(f'Skipped {output} (already exists)')
                continue
            pool.apply_async(partial(rasterize, i, output, size=80, quality=101))
            success_counter += 1

        pool.close()
        pool.join()

    if success_counter:
        print(f'Rasterized {success_counter} SVGs in {time.ms}ms')


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
