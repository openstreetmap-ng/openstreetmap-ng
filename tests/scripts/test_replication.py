from inspect import unwrap
from pathlib import Path

import polars as pl
import pytest

from scripts.replication import AppState, ReplicaState, _iterate


@pytest.mark.extended
async def test_iterate():
    state = AppState(
        frequency='hour',
        last_replica=ReplicaState.default(),
        last_sequence_id=0,
    )
    state = await unwrap(_iterate)(state)
    path: Path = state.last_replica.path
    assert path.is_file()
    try:
        df = pl.read_parquet(path)
        assert df.shape == (156829, 12)
    finally:
        path.unlink(missing_ok=True)
