# Inline tag editor frontend contract

This implements the frontend-only scope in issue #90:
https://github.com/openstreetmap-ng/openstreetmap-ng/issues/90#issuecomment-2241735956

The current sidebar uses Preact. Its tag section hosts a clone of a server-rendered
Jinja form from `index/_tag-editor`, available only on signed-in map pages. Editing
is offered only for visible elements without a next version. The component is
keyed by element type, ID and version, so navigating to another element disposes
the old form and unsaved values.

The host contains a single JSON `data-tags` attribute. Edit fills the textarea
with raw `key=value` lines. Discard clears both fields and restores the original
tag table and Edit button. The required comment also rejects whitespace-only
input. Version is submitted alongside tags and comment.

The native POST targets the current canonical element URL (`/node/ID`, `/way/ID`
or `/relation/ID`). **There is no POST handler or persistence in this PR.** On
current main, submitting reaches an unsupported route; no successful save is
claimed. The issue explicitly defers backend integration until API 0.7. Before
shipping this interface, the backend work must agree/finalize the action and
field contract, authorize the change, enforce the submitted version, validate
tags and create the changeset. This PR neither intercepts the submit event nor
simulates a successful save.

Local checks exercised the actual rendered Jinja form and production controller
in jsdom: anonymous exclusion, raw/HTML-containing values, action/version,
required nonblank comment, uncancelled submit, discard/reset, and disposal.
Changed TS/TSX files transpiled and were formatted. Full map/API integration
requires the project's Nix runtime and is not claimed as locally verified.
