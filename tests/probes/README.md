# Changeset note closure probe

```sh
uv run --no-project --python 3.14 python tests/probes/changeset_notes.py
```

Eight isolated cases execute actual source AST for the parser, transactional
note helper, manual changeset close, inactive close and OptimisticDiff.run.
DB calls, SQL execution, transaction rollback storage, authentication, audit,
bootstrap and native components are explicit doubles; this probe does not
establish real PostgreSQL locking/rollback or HTTP correctness. It verifies
connection reuse, ordering and the actual integration call sites, not a copy
of the production parser. The fake notification checks that commit was seen
first and the comment is attributed to the changeset owner.

For the before/after counterexamples:

```sh
uv run --no-project --python 3.14 python tests/probes/changeset_notes.py --baseline /path/to/base Tests.test_manual_real_method_wiring Tests.test_inactive_real_method_wiring Tests.test_size_limit_actual_run
```

On exact base5cddbe2 all three original closure methods leave the test notes
open. `tests/services/test_changeset_notes.py` additionally contains9 normal
project pytest cases (5 parser parameters and4 real API/database scenarios).
Two follow-up DB cases add synchronized concurrent closures of one note and
hidden-note skip behavior. The concurrency case puts both real transactions at
a barrier before the actual row-lock query; it expects one close event and one
notification with both changesets closed. These also require the full project
environment and were not run locally.

Those require the full project environment. They were not run locally; a probe
pass is not a DB suite pass. The real notification scheduler is reused, while
the integration tests replace outbound notification delivery. No live notes,
mail recipients or user credentials are used by the local probe.

Missing, hidden and already-closed notes are skipped; empty overrides suppress
fallback text. Audit uses the existing application audit function, whose normal
background/no-request behavior may skip request-only audit records. No new
durable mail outbox is introduced: post-commit notification failures retain the
same delivery limitation as existing manual note comments.
