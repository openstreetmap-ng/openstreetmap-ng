# Edit-help browser regression tests

Run from the repository root with Bun and Chromium installed by Playwright:

```sh
bun test --timeout 15000 tests/frontend/edit-help.test.ts
```

The harness needs `esbuild`, `playwright`, `bootstrap` (5.3.8), `@popperjs/core`, `preact`, `@preact/signals`, and `zod`. They can be installed in an isolated directory without changing this project's manifest. Set `FRONTEND_TEST_NODE_MODULES` and `NODE_PATH` to that directory's `node_modules` when using an isolated installation. Install the browser with `playwright install chromium` from that tooling directory.

Tests bundle the actual NavbarLeft component, router, query-string/query-contract helpers, and dispose scopes, using real Preact signals and Bootstrap tooltips/collapse. The small fixture replaces authentication, translation, map state, remote editing, and standard-library primitives. Routes are parameter-free fixtures; no backend, external tiles or API is called. All non-loopback browser requests are blocked. Optional `EDIT_HELP_EVIDENCE` points to an existing directory for desktop/mobile screenshots.

Coverage includes exact query gating, mobile expansion, disabled-zoom tooltip exclusion/restoration, click dismissal preserving history state/query/hash, identical-URL reactivation via actual router anchor interception, navigation cleanup, and component unmount cleanup. This is scoped browser integration coverage, not a full application build or physical-device test.
