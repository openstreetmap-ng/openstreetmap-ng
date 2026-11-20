# Bounded native changeset diff

Run with the project's Bun runtime and installed Playwright/Chrome:

```sh
bun test tests/views/changeset-diff
```

Set `PLAYWRIGHT_PACKAGE` when Playwright lives outside the checkout and
`EVIDENCE_DIR` for screenshots. The browser test runs an ephemeral HTTP fixture
and closes the browser/server on completion.

Five core cases exercise actual grouping, rendering and polyline code. The
three browser cases use the actual control, dispose scopes, generated service
descriptors, protobuf request/response roundtrips and real MapLibre WebGL.
Desktop1280/mobile390 verify colored nonblank canvas pixels, rendering of node
and way before/after states, mode selection, style reload, close/unmount
cleanup, failure/retry, abort and the oversized-request guard.

The version provider returns controlled synthetic data. DB, auth, real RPC
transport, production basemap assets/CSS and full sidebar/router mounting are
not covered. Only the unused generic map-layer helper import is replaced;
MapLibre, the diff layers and rendering are not mocked. Screenshots show the
fixture's plain background, not a production basemap. The source language file
is read, not a hand-translated fixture. Browser readback uses the installed
MapLibre public getData API and its canvasContextAttributes option.

Production uses the existing versioned RPC and real changeset sidebar data.
Multiple edits to one object use its first changeset version minus1 and its
last version. Relations are explicitly reported as unsupported geometry. More
than200 distinct nodes/ways shows a limit error without any version requests,
not a truncated success; reads are bounded to4 concurrent requests. No claim
of full Achavi parity, tag diff, relations, large-change streaming, full Nix
build, type gate or HTTP/DB integration is made by these tests.
