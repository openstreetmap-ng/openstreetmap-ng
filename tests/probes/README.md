# Null Island probe

Run from the repository root:

```sh
uv run --no-project --python 3.14 --with shapely --with fastapi python tests/probes/null_island.py
```

This executes the current source AST of `OptimisticDiffPrepare.prepare`, its
guard, the real `user_is_moderator` function, and the default error method.
Shapely points and FastAPI HTTP exceptions are real. DB/preloads, bounds,
reference operations, native typed-id decoding and application startup are
explicit boundaries; the probe does not validate a real transaction or HTTP
request. It runs outside pytest because the root autouse fixture requires the
full database/application environment.

The 10 cases cover the threshold, single/empty uploads, exact coordinates,
deleted/non-node entries, distinct final node state, privileged bypass and the
actual preparation call site. The project pytest integration file
`tests/services/optimistic_diff/test_null_island.py` adds 5 database cases,
including both privileged roles. Those require the normal project environment;
a standalone probe pass is not evidence that they passed.

For the baseline counterexample, use the same probe and an exact base worktree:

```sh
uv run --no-project --python 3.14 --with shapely --with fastapi python tests/probes/null_island.py --source-root /path/to/base GuardTests.test_actual_prepare_rejects_before_apply
```

On base `5cddbe2ab24be38111e637ed0de59d1ad88a0a31` this fails with
`HTTPException not raised`. This exercises the original preparation loop, not
a reimplemented guard. The feature deliberately concerns distinct visible
edited nodes in the final state of one upload. It does not query earlier
uploads in the changeset, reject single-node notes/traces or untouched way
members, or add audit/anti-vandalism infrastructure.
