import subprocess
from multiprocessing.pool import AsyncResult, Pool
from os import utime
from pathlib import Path

_POSTPROCESS_DIR = Path('config/locale/postprocess')
_GNU_DIR = Path('config/locale/gnu')
_GNU_DIR.mkdir(parents=True, exist_ok=True)


def transform(
    source_path: Path,
    effective_mtime: float,
    *,
    target_path_po: Path,
    target_path_mo: Path,
) -> None:
    locale = source_path.stem
    target_path_po.parent.mkdir(parents=True, exist_ok=True)

    # transform json to po
    subprocess.run(
        [
            'pnpm',
            'exec',
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
    utime(target_path_po, (effective_mtime, effective_mtime))
    utime(target_path_mo, (effective_mtime, effective_mtime))


def main() -> None:
    script_mtime = Path(__file__).stat().st_mtime

    with Pool() as pool:
        discover_counter = 0
        jobs: list[AsyncResult[None]] = []

        for source_path in _POSTPROCESS_DIR.glob('*.json'):
            discover_counter += 1
            locale = source_path.stem
            source_mtime = source_path.stat().st_mtime
            effective_mtime = max(source_mtime, script_mtime)
            target_path_po = _GNU_DIR.joinpath(locale, 'LC_MESSAGES/messages.po')
            target_path_mo = target_path_po.with_suffix('.mo')
            if (
                target_path_mo.is_file()
                and effective_mtime <= target_path_mo.stat().st_mtime
            ):
                continue

            jobs.append(
                pool.apply_async(
                    transform,
                    (source_path, effective_mtime),
                    {
                        'target_path_po': target_path_po,
                        'target_path_mo': target_path_mo,
                    },
                )
            )

        pool.close()
        pool.join()
        for job in jobs:
            job.get()

    print(
        f'[gnu] Discovered {discover_counter} locales, transformed {len(jobs)} locales',
    )


if __name__ == '__main__':
    main()
