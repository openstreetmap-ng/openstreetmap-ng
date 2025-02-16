import os
import subprocess
from functools import partial
from multiprocessing.pool import Pool
from pathlib import Path

import click

_postprocess_dir = Path('config/locale/postprocess')
_gnu_dir = Path('config/locale/gnu')
_gnu_dir.mkdir(parents=True, exist_ok=True)


def transform(source_path: Path, source_mtime: float, *, target_path_po: Path, target_path_mo: Path) -> None:
    locale = source_path.stem
    target_path_po.parent.mkdir(parents=True, exist_ok=True)

    # transform json to po
    subprocess.run(
        [
            'bunx',
            'i18next-conv',
            '--quiet',
            '--language',
            locale,
            '--source',
            str(source_path),
            '--target',
            str(target_path_po),
            '--keyseparator',
            '.',
            '--ctxSeparator',
            '__',
            '--compatibilityJSON',
            'v4',
        ],
        check=True,
    )

    with target_path_po.open('r+') as f:
        # convert {{placeholder}} to {placeholder}
        temp = f.read().replace('{{', '{').replace('}}', '}')
        f.seek(0)
        f.write(temp)
        f.truncate()

    # compile po to mo
    subprocess.run(
        [
            'msgfmt',
            str(target_path_po),
            '--output-file',
            str(target_path_mo),
        ],
        check=True,
    )

    # preserve mtime
    os.utime(target_path_po, (source_mtime, source_mtime))
    os.utime(target_path_mo, (source_mtime, source_mtime))


@click.command()
def main() -> None:
    with Pool() as pool:
        discover_counter = 0
        success_counter = 0
        for source_path in _postprocess_dir.glob('*.json'):
            discover_counter += 1
            locale = source_path.stem
            source_mtime = source_path.stat().st_mtime
            target_path_po = _gnu_dir.joinpath(locale, 'LC_MESSAGES/messages.po')
            target_path_mo = target_path_po.with_suffix('.mo')
            if target_path_mo.is_file() and source_mtime <= target_path_mo.stat().st_mtime:
                continue

            pool.apply_async(
                partial(
                    transform,
                    source_path,
                    source_mtime,
                    target_path_po=target_path_po,
                    target_path_mo=target_path_mo,
                )
            )
            success_counter += 1
        pool.close()
        pool.join()

    discover_str = click.style(f'{discover_counter} locales', fg='green')
    success_str = click.style(f'{success_counter} locales', fg='bright_green')
    click.echo(f'[gnu] Discovered {discover_str}, transformed {success_str}')


if __name__ == '__main__':
    main()
