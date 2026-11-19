# Edit help browser regression

Run from the repository root with Bun and Playwright installed:

```sh
bun test tests/views/navbar/edit-help.test.ts
```

The default browser channel is Chrome. Set `PLAYWRIGHT_CHANNEL` to another
installed Chromium channel, or `PLAYWRIGHT_PACKAGE` to an existing Playwright
module entry point when using an external test-tool installation.

The fixture bundles the real navbar, router, Bootstrap tooltip and Preact
components. Login configuration, map state, map layers, remote editor and stored
editor preference are explicit boundary replacements. It is not an authenticated
full-application or map-rendering test. No backend or account is used.

The tests cover the requested hint, first-click completion, query and hash
preservation, replacement history, signed-out and non-1 requests, SPA re-entry,
restoration of the disabled-edit tooltip, mobile collapse, viewport transitions,
navigation and browser back, and browser errors.

Full application validation still requires the documented Nix development
environment and backend services.
