from inspect import unwrap
from pathlib import Path

import pyarrow.parquet as pq
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
        metadata = pq.read_metadata(path)
        assert metadata.num_columns == 12
        assert metadata.num_rows == 156829
    finally:
        path.unlink(missing_ok=True)
