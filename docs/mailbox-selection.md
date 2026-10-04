# Mailbox selection, bulk read state and deletion

Incremental implementation of #165, which explicitly allows incremental work.

Delivered:
- Select individual inbox messages without opening them.
- Select/deselect all messages visible on the current page.
- Display the total selected count, including other pages.
- Keep selection while paging; clear it when switching mailbox or leaving the page.
- Mark selected messages read or unread using existing authenticated RPCs.
- Delete selected inbox messages after confirming the total across all pages.
- Remove completed deletions from the list and selection, closing an affected preview.
- Decrement the unread badge from the atomic server deletion result, including
  for off-page selections; repeated deletion does not decrement it again.
- Update the global unread badge only when the server reports an actual change.
- Stop on failure and retain the failed and unprocessed selections for retry.
- Stop remaining mutations after mailbox navigation; an already-sent RPC may finish.
- Search inbox senders, outbox recipients and subjects with case-insensitive literal
  substrings. Percent and underscore characters are not treated as wildcards.
- Filter by inclusive timestamps entered in local time. Filters apply on the server
  across the mailbox, preserve ownership restrictions, and are retained in the URL.
- Applying different filters resets pagination, preview and selection. Paging and
  opening or closing a preview retain the active filters.

Requests run sequentially. A second bulk operation and selection changes are disabled
while processing. The existing message service continues to enforce ownership.

Age-based review: enter 1–100 days, weeks, months or years to replace the current
filters with a strict upper timestamp bound. Calendar arithmetic uses UTC and
clamps month/year subtraction to the last valid day (including leap years).
The absolute cutoff is retained in the URL. Review the resulting messages, select
them across pages and use Delete selected with the existing confirmation.
This does not automatically select or delete every matching message. The issue's
$30 label covers the overall issue; no particular payment allocation is claimed.

Validation: production selection runner exercised for sequential completion,
partial failure and navigation invalidation. Changed TS/TSX files transpile with
esbuild and pass oxfmt. Full authenticated application integration requires the
project Nix environment and has not been run locally.

The RPC CRUD regression also checks the unread deletion flag and idempotent retry;
it requires the project database and generated protobuf bindings to run in CI.
The production mailbox component was also exercised with mocked RPC/pagination:
cancel confirmation, delete off-page selections, stop on partial failure, retry
only remaining selections, and update the unread badge. Local Cython conversion
of the modified message service passed.

Filter validation: compiled protobuf descriptors accept valid boundaries and reject
reversed dates, out-of-range timestamps, empty searches and oversized searches.
The component harness checks filter reset and selection clearing. Added database RPC
regressions for sender/recipient matching, literal characters, date ranges, mailbox
ownership and hidden messages; these require upstream CI. Ruff, buf lint/build,
TSX transpilation and local Cython conversion of the query/RPC modules passed.

Upstream run 34685753433: Python suites passed on macOS and Ubuntu; Cython
reported 614 passing tests, then failed during interpreter shutdown with
`gilstate_tss_set: failed to set current tstate (TSS)`. The Cython job is not green.

Age review validation: actual helper tested for March 31 → February 29, leap-day
year subtraction, UTC days/weeks, strict integer-second cutoffs and epoch clamp.
The production component harness confirms review changes the query without any
mutation RPC and leaves Delete selected disabled until messages are selected.
