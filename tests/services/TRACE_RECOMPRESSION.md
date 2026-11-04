# Trace recompression regression tests

Inside the project's configured Nix shell, start normal development/test services with `dev-start`. Provide a **dedicated test database** whose user may create and drop schemas:

```sh
OSM_TRACE_TEST_DSN='host=127.0.0.1 dbname=osm_trace_test user=test_user' \
  run-tests tests/lib/test_trace_file.py tests/services/test_trace_recompression.py
```

Without `OSM_TRACE_TEST_DSN`, the PostgreSQL lifecycle tests skip. Each test creates a uniquely named `trace_recompression_*` schema and drops only that schema afterwards. No existing table is modified.

The tests execute the production compression, upload/deletion/recompression worker, query download retry and shutdown context. Database adapters execute real conditional updates, commits, rollbacks and row locks. Storage is an in-memory API substitute holding actual zstd bytes; upload parsing/authentication/audit/validation and visibility are stubbed. S3 failures use botocore ClientError objects without network calls. Fixtures are only a few KB.

Coverage includes upload responsiveness after commit, metadata/roundtrip preservation, file replacement and cleanup, both deletion race orders, stale ownership, failures/cancellation, lost commit acknowledgement, concurrent downloads and shutdown cleanup. These scoped tests do not substitute for a full application test run. Local verification used PostgreSQL17; the supported production stack uses PostgreSQL18.
