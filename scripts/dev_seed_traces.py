import logging
import random
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from hashlib import pbkdf2_hmac
from queue import Queue
from threading import Lock
from time import monotonic
from urllib.parse import urlparse

import httpx

from app.models.proto.shared_pb2 import IdResponse, TransmitUserPassword

_CITY_CENTERS: list[tuple[str, float, float]] = [
    ('san_francisco', 37.7749, -122.4194),
    ('new_york', 40.7128, -74.0060),
    ('london', 51.5072, -0.1276),
    ('berlin', 52.52, 13.405),
    ('tokyo', 35.6895, 139.6917),
    ('sydney', -33.8688, 151.2093),
]


def _parse_args():
    parser = ArgumentParser(
        description=(
            'Dev-only helper: create many random-ish GPX traces via the web API.\n'
            'Intended for manual pagination performance testing.'
        )
    )
    parser.add_argument('--base-url', default='http://localhost:8000')

    auth_group = parser.add_mutually_exclusive_group(required=True)
    auth_group.add_argument(
        '--dev-user',
        help="Dev/test auth via 'Authorization: User <display_name>' (no cookies/login).",
    )
    auth_group.add_argument(
        '--auth-cookie',
        help="Existing 'auth' cookie value (bypasses login).",
    )
    auth_group.add_argument('--display-name-or-email')

    parser.add_argument(
        '--password',
        help='Password for --display-name-or-email (PBKDF2-v1, like the browser).',
    )

    parser.add_argument('--count', type=int, default=10_000)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--concurrency', type=int, default=16)
    parser.add_argument('--points', type=int, default=80)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument(
        '--visibility',
        default='mix',
        choices=('public', 'identifiable', 'trackable', 'private', 'mix'),
    )
    parser.add_argument(
        '--allow-nonlocal',
        action='store_true',
        help='Allow running against non-local base URLs (dangerous).',
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=('DEBUG', 'INFO', 'WARNING', 'ERROR'),
    )
    return parser


def _is_local_base_url(url: str):
    host = urlparse(url).hostname
    return host in {'127.0.0.1', 'localhost', None}


def _origin_from_base_url(url: str):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f'Invalid --base-url: {url!r}')
    return f'{parsed.scheme}://{parsed.netloc}'


def _build_transmit_password_v1(password: str, *, origin: str):
    salt = f'{origin}/zaczero@osm.ng'.encode()
    password_bytes = pbkdf2_hmac(
        'sha512',
        password.encode(),
        salt=salt,
        iterations=100_000,
        dklen=64,
    )
    return TransmitUserPassword(v1=password_bytes).SerializeToString()


def _pick_visibility(rng: random.Random, mode: str):
    if mode != 'mix':
        return mode
    # Keep most traces visible in public listings.
    return 'public' if rng.random() < 0.8 else 'identifiable'


def _wrap_lon(lon: float):
    if lon > 180:
        return lon - 360
    if lon < -180:
        return lon + 360
    return lon


def _clamp_lat(lat: float):
    if lat > 89.9:
        return 89.9
    if lat < -89.9:
        return -89.9
    return lat


def _random_walk_points(
    rng: random.Random,
    *,
    center_lat: float,
    center_lon: float,
    points: int,
):
    lat = center_lat + rng.uniform(-0.05, 0.05)
    lon = center_lon + rng.uniform(-0.05, 0.05)
    out: list[tuple[float, float]] = []
    for _ in range(points):
        lat = _clamp_lat(lat + rng.uniform(-0.0008, 0.0008))
        lon = _wrap_lon(lon + rng.uniform(-0.0012, 0.0012))
        out.append((lat, lon))
    return out


def _build_gpx(points: list[tuple[float, float]], *, name: str):
    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="openstreetmap-ng-dev-seed" xmlns="http://www.topografix.com/GPX/1/1">',
        '<trk>',
        f'<name>{name}</name>',
        '<trkseg>',
    ]
    for lat, lon in points:
        parts.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}"></trkpt>')
    parts.extend(['</trkseg>', '</trk>', '</gpx>'])
    return ''.join(parts).encode()


def _login_and_get_cookie(
    client: httpx.Client, *, base_url: str, who: str, password: str
):
    origin = _origin_from_base_url(base_url)
    transmit_password = _build_transmit_password_v1(password, origin=origin)
    resp = client.post(
        f'{origin}/api/web/user/login',
        data={'display_name_or_email': who, 'remember': 'true'},
        files={
            'password': (
                'password.bin',
                transmit_password,
                'application/octet-stream',
            )
        },
        headers={'Accept': '*/*'},
    )

    if resp.status_code == 204:
        auth_cookie = client.cookies.get('auth')
        if not auth_cookie:
            raise RuntimeError("Login succeeded but 'auth' cookie missing.")
        return auth_cookie

    if resp.status_code == 200 and resp.headers.get('Content-Type', '').startswith(
        'application/x-protobuf'
    ):
        raise RuntimeError(
            'Login requires additional steps (2FA/passkey). Use --auth-cookie or --dev-user instead.'
        )

    raise RuntimeError(f'Login failed: {resp.status_code} {resp.text[:200]}')


def _upload_one(
    client: httpx.Client,
    *,
    base_url: str,
    index: int,
    rng_seed: int,
    points: int,
    visibility_mode: str,
):
    rng = random.Random(rng_seed + index)
    city_name, city_lat, city_lon = rng.choice(_CITY_CENTERS)

    trace_points = _random_walk_points(
        rng,
        center_lat=city_lat,
        center_lon=city_lon,
        points=points,
    )
    trace_name = f'dev-seed-{city_name}-{index:06d}'
    gpx_bytes = _build_gpx(trace_points, name=trace_name)

    tags = [city_name, rng.choice(('walk', 'bike', 'run', 'hike'))]
    visibility = _pick_visibility(rng, visibility_mode)

    resp = client.post(
        f'{base_url.rstrip("/")}/api/web/traces/upload',
        files=[
            ('description', (None, f'Dev seed trace {index} ({city_name})')),
            ('visibility', (None, visibility)),
            *[('tags', (None, tag)) for tag in tags],
            (
                'file',
                (
                    f'{trace_name}.gpx',
                    gpx_bytes,
                    'application/gpx+xml',
                ),
            ),
        ],
        headers={'Accept': 'application/x-protobuf'},
    )
    resp.raise_for_status()
    id_resp = IdResponse.FromString(resp.content)
    return int(id_resp.id)


def main():
    parser = _parse_args()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    logging.getLogger('httpx').setLevel(
        logging.INFO if args.log_level == 'DEBUG' else logging.WARNING
    )

    if not args.allow_nonlocal and not _is_local_base_url(args.base_url):
        raise SystemExit(
            f'Refusing to run against non-local --base-url={args.base_url!r}. '
            'Pass --allow-nonlocal if you really mean it.'
        )

    if args.display_name_or_email and not args.password:
        raise SystemExit('--password is required when using --display-name-or-email.')

    total = args.count
    start = args.start
    end = start + total
    if total <= 0:
        raise SystemExit('--count must be > 0.')

    base_url = args.base_url.rstrip('/')

    auth_cookie: str | None = args.auth_cookie
    auth_header: str | None = None
    if args.dev_user:
        auth_header = f'User {args.dev_user}'
    elif auth_cookie is None:
        with httpx.Client(
            timeout=httpx.Timeout(60.0), follow_redirects=False
        ) as client:
            auth_cookie = _login_and_get_cookie(
                client,
                base_url=base_url,
                who=args.display_name_or_email,
                password=args.password,
            )

    created = 0
    failed = 0
    error_logs = 0
    last_log = 0
    t0 = monotonic()
    lock = Lock()

    queue: Queue[int | None] = Queue()
    for i in range(start, end):
        queue.put(i)
    for _ in range(args.concurrency):
        queue.put(None)

    def worker(worker_id: int):
        nonlocal created, failed, error_logs, last_log

        with httpx.Client(
            timeout=httpx.Timeout(60.0),
            follow_redirects=False,
            limits=httpx.Limits(
                max_connections=8,
                max_keepalive_connections=8,
            ),
            headers={'Authorization': auth_header} if auth_header else None,
            cookies={'auth': auth_cookie} if auth_cookie else None,
        ) as client:
            while True:
                i = queue.get()
                if i is None:
                    return

                try:
                    _upload_one(
                        client,
                        base_url=base_url,
                        index=i,
                        rng_seed=args.seed,
                        points=args.points,
                        visibility_mode=args.visibility,
                    )
                    with lock:
                        created += 1
                except Exception:
                    with lock:
                        failed += 1
                        if error_logs < 10:
                            error_logs += 1
                            logging.exception('Failed to upload trace %d', i)

                with lock:
                    if created + failed - last_log >= 100:
                        last_log = created + failed
                        dt = monotonic() - t0
                        rate = (created + failed) / dt if dt else 0.0
                        logging.info(
                            'Progress: %d/%d (created=%d failed=%d) %.1f req/s',
                            created + failed,
                            total,
                            created,
                            failed,
                            rate,
                        )

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        for worker_id in range(args.concurrency):
            executor.submit(worker, worker_id)

    dt = monotonic() - t0
    logging.info(
        'Done: created=%d failed=%d total=%d in %.1fs (%.1f req/s)',
        created,
        failed,
        total,
        dt,
        (created + failed) / dt if dt else 0.0,
    )


if __name__ == '__main__':
    main()
