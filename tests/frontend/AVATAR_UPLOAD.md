# Image-upload browser regression tests

Run from the repository root with Bun and Playwright's Chromium installed:

```sh
bun test --timeout 15000 tests/frontend/avatar-upload.test.ts
```

The harness needs `esbuild`, `playwright`, `bootstrap` (5.3.8), `@popperjs/core`, `preact`, and `@preact/signals`. They may be installed in an isolated tooling directory; set `FRONTEND_TEST_NODE_MODULES` to its `node_modules` directory. Install Chromium with `playwright install chromium` from that tooling directory.

Tests bundle the actual `StandardForm`, file helper, feedback renderer and disposal scopes. The fixture replaces RPC, configuration, translation and unrelated application imports. It uses an eight-byte test limit, exercising oversized files without large allocations. No production service or external browser request is used.

Coverage includes desktop/mobile feedback before file reading or RPC, retry after failure, error clearing, and empty-file preset/removal semantics. This is scoped form integration coverage; it does not start the full profile page or backend.
