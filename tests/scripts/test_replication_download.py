from inspect import unwrap
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from scripts.replication_download import (
    AppState,
    ReplicaState,
    _iterate,  # noqa: PLC2701
)


@pytest.mark.extended
async def test_iterate():
    # Create initial state
    state = AppState(
        frequency='hour',
        last_replica=ReplicaState.default(),
        last_sequence_id=0,
        last_versioned_refs=[],
    )

    # Iterate once
    state = await unwrap(_iterate)(state)

    # Verify the file was created
    path: Path = state.last_replica.path
    assert path.is_file()

    try:
        # Verify the file has the expected layout
        metadata = pq.read_metadata(path)
        assert metadata.num_columns == 13
        assert metadata.num_rows == 156829
    finally:
        path.unlink(missing_ok=True)

    # Verify state was updated
    assert state.frequency == 'hour'
    assert state.last_sequence_id == 156829
    assert len(state.last_versioned_refs) == 156829
