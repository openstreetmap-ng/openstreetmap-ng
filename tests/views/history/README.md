# Configurable history page-size checks

The UI offers the server's existing default plus25/50/100 versions per page.
Unsupported URL values use that default; API clients may send any limit1..100.
An omitted/zero RPC field retains the old default. Changing the UI selection
preserves other URL parameters/hash, removes the previous page number, and pushes
a history entry. The existing StandardPagination wrapper keys resources by the
serialized request, so changing limit replaces its old cursor resource.

Build the actual current descriptor (Buf1.75.0 used locally):

```sh
buf lint
buf build --as-file-descriptor-set -o /tmp/history.binpb
HISTORY_DESCRIPTORS=/tmp/history.binpb uv run --no-project --python 3.14 --with protobuf==6.33.6 --with protovalidate --with cython==3.2.4 --with pytest==9.0.3 python tests/views/history/probe.py
```

The two Python tests use actual protobuf descriptors and protovalidate, wire
roundtrips, omitted-field compatibility and rejection above100. The second test
executes the actual get_history method body and actual sp_num_pages/_ceil_div
functions extracted with Python's AST, in interpreted CPython3.14. It replaces
database pagination, SQL constructors, native typed-ID conversion and startup
dependencies, returning an empty element list with a real protobuf state. It
checks query page_size and known totals for0/1/10/25/50/100, not real row retrieval,
full Connect middleware, or compiled Cython. This is deliberately not presented
as a complete application import or integration test.

For a baseline, HISTORY_HANDLER_SOURCE may point to exactmain's app/rpc/element.py;
non-default limits then fail against the same current request contract. Buf
breaking checks against a descriptor built from that exact worktree also pass
for this additive field (use `#format=binpb` when the extension is `.pb`).

```sh
bun test tests/views/history/browser.test.ts
```

The three browser cases bundle the actual history sidebar and helper, real
Preact/i18next and URL-state code. They check desktop/mobile, valid/invalid limits,
request payloads, page removal, unrelated coordinates/hash and Back navigation.
Map, router registration, protobuf service descriptor, tags and pagination
loading/rendering are explicit boundary replacements. They do not run the actual
StandardPagination cursor state machine, map scene, production styles or generated
locale pipeline; the existing request-key behavior is verified by source review,
not claimed as executed here. English source strings are normalized for i18next.

Playwright/Chrome must be installed. PLAYWRIGHT_PACKAGE can identify an existing
module. HISTORY_SOURCE can identify an original sidebar for the missing-control
RED assertion; HISTORY_SCREENSHOTS is an optional screenshot prefix.

Normal project proto generation must run before the full application is built.
Local Buf build/lint/breaking and dynamic wire validation do not claim that the
complete generated Python/TypeScript pipeline, full type gate, Nix services, auth,
database, or Cython build were executed. Generated bindings and locks are not
committed. Targeted Ruff passes for the probe; the RPC module's I001 is also
present on the exact baseline with absent generated bindings, so unrelated
imports were not reordered and its other rules were checked separately.
