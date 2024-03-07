import anyio
import numpy as np

from app.utils import HTTP


async def benchmark(url: str, *, warmup: int = 5, num: int = 100) -> list[float]:
    times = []

    for _ in range(warmup):
        await HTTP.get(url)

    for _ in range(num):
        r = await HTTP.get(url)
        time = float(r.headers.get('X-Runtime'))
        times.append(time)

    return times


# ruby
# Min: 0.04264s
# Median: 0.04521s

# official
# Min: 0.01892s
# Median: 0.02921s

# test
# Min: 0.00913s
# Median: 0.01725s

# python
# Min: 0.00314s
# Median: 0.00325s


async def main():
    for url in ['http://127.0.0.1:8000/copyright']:
        print(f'Benchmarking {url}...')
        times = await benchmark(url)

        min_ = np.min(times)
        print(f'Min: {min_:.5f}s')
        median = np.median(times)
        print(f'Median: {median:.5f}s')


if __name__ == '__main__':
    anyio.run(main)
