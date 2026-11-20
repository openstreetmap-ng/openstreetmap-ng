# Mailbox selection regression tests

This is an incremental contribution to issue #165: selection and bulk actions,
not search, date filters, or age-based cleanup. It uses existing per-message RPCs;
there is no new bulk endpoint or atomic all-or-nothing transaction.

Run with Bun and an installed Playwright/Chrome:

```sh
bun test --timeout 20000 tests/views/messages/index.test.ts
```

`PLAYWRIGHT_PACKAGE` may point to an installed Playwright module. Optional
`MAILBOX_SCREENSHOT` and `MAILBOX_DESKTOP_SCREENSHOT` capture the mobile failure
state and desktop page. `MAILBOX_SOURCE` can point to the original index.tsx in
a separate baseline worktree with dependencies installed.

The browser bundles the actual production messages/index.tsx and batch helper,
with real Preact signals/hooks, i18next translations, Bootstrap and icon fonts.
It clicks the actual controls, including their stretched-link hit areas.
RPC/protobuf, authentication/page mounting, URL routing, pagination data/loading,
navbar badge storage, time/user links, and report controls are explicit test
boundaries. Shared social positioning and button styling are a small CSS subset,
not the complete application stylesheet. Pagination is a two-page fixture, not
the real StandardPagination loader or a database integration test.

The tests cover cross-page selection and clearing visible selections, exact
selected-ID RPC dispatch, partial failures and retry, disabled controls while
pending, unchanged-state badge handling, delete cancellation, and mailbox changes
during an active batch. A switch stops later queued calls, but cannot undo an
already accepted request. Deletion retains the existing single-message API and
navbar-badge behavior; it does not infer an unread delta from stale row metadata.

Full Nix/backend/authenticated HTTP tests, the locale generation pipeline, full
project type checking and production styling are not validated by this harness.
