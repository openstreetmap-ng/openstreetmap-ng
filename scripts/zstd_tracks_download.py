import random

import httpx
from tqdm import tqdm

NUM_FILES = 1000
MAX_FILE_SIZE = 128 * 1024  # 128 KiB

print('WARNING! Dictionaries ARE NOT backwards compatible.')
print('WARNING! Dictionaries ARE NOT backwards compatible.')
print('WARNING! Dictionaries ARE NOT backwards compatible.')

USERNAME = input('Username: ')
PASSWORD = input('Password: ')

HTTP = httpx.Client(
    base_url='https://api.openstreetmap.org/api/0.6/',
    auth=httpx.BasicAuth(USERNAME, PASSWORD),
    follow_redirects=True,
    http1=True,
    http2=True)

PROCESSED = set()

random.seed(42)

for i in tqdm(range(NUM_FILES)):
    while True:
        track_id = random.randint(10000000, 11148369)
        if track_id in PROCESSED:
            continue

        PROCESSED.add(track_id)

        r = HTTP.get(f'gpx/{track_id}/data')

        if not r.is_success or r.num_bytes_downloaded > MAX_FILE_SIZE:
            continue
        if not r.content.startswith(b'<?xml'):
            continue

        with open(f'zstd/tracks/{track_id}.gpx', 'wb') as f:
            f.write(r.content)

        break
