# OpenStreetMap‑NG

This is the single set of ground rules for this repo. It orients new contributors, captures the most common patterns, and points to canonical examples to copy. The project is under active development; breaking changes are acceptable.

## Project At A Glance

- Backend: Python 3.13, FastAPI, async Psycopg 3, PostgreSQL 18 (PostGIS, TimescaleDB). Optional acceleration via Cython (pure‑Python mode) and `speedup` Rust extension (PyO3).
- Frontend: Jinja2 server‑rendered HTML; Vite‑bundled TypeScript (ES2023) and SCSS; Bootstrap 5 + Bootstrap Icons; MapLibre GL.
- Tooling: Reproducible dev shell (`shell.nix`), Python deps via `uv`, TS/JS via `bun`, formatting with Ruff/Biome, type checks with BasedPyright.

## Repository Map

- `app/controllers/` — FastAPI routers; keep thin; orchestrate services/queries.
- `app/lib/` — Cross‑cutting helpers (translation, rendering, auth context, HTTP, Vite, date/utils).
- `app/middlewares/` — Request/translation contexts, CORS, cache‑control, profiling, unsupported browser.
- `app/models/db/` — Row `TypedDict`s mirroring tables plus helpers.
- `app/models/proto/` — Protobuf schemas + generated Python.
- `app/queries/` — Pure SELECT data access; compose dynamic SQL safely.
- `app/responses/` — Response helpers including `PrecompressedStaticFiles` for `.zst`/`.br` assets.
- `app/services/` — Mutations and workflows (write paths, audits, email, OAuth2). Use `db(write=True)`.
- `app/static/` — Built assets; Vite outputs to `app/static/vite/`.
- `app/views/` — Templates (`*.html.jinja`) + feature‑scoped TypeScript/SCSS; shared libs in `app/views/lib/`.
- `config/locale/` — Locale sources and generated outputs.
- `scripts/` — Pipelines (locale, proto, raster, replication).
- `shellscripts/` — Dev shell commands (loaded by `shell.nix`); `*.sh` for plain bash, `*.nix` when Nix features are needed. Do not execute directly. Generated command name matches the filename.
- `speedup/` — Optional Rust extension for hot paths (PyO3/maturin).
- `tests/` — Pytest suite mirroring `app/` layout.
- Root configs: `vite.config.ts`, `tsconfig.json`, `package.json`, `pyproject.toml`, `biome.json`, `shell.nix`.

## Development Workflow

Application Server:

```sh
run
# INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
# INFO: Started reloader process [...] using WatchFiles
```

Code Quality:

```sh
format                # Format/lint/non-Python type checks
pyright               # Python type checks (BasedPyright)
run-tests             # Standard pytest suite
run-tests --extended  # Extended tests marked with @pytest.mark.extended
```

Asset Pipelines:

```sh
proto-pipeline        # Compile Protobuf → Python + TypeScript
locale-pipeline       # Build GNU gettext + i18next bundles (with pruning)
watch-locale          # Watch extra_en.yaml and rebuild locales on change
watch-proto           # Watch .proto files and regenerate on change
vite build            # Build TypeScript/SCSS (alternatively: vite-build helper)
static-precompress    # Produce .zst/.br for large static assets
```

## Backend Conventions

- Layering: controller → service → query. Controllers validate and orchestrate; services mutate; queries are side‑effect‑free. Read‑only lookup methods (even complex ones combining multiple conditions) belong in queries, not services.
- Database access: always use `app/db.py:db(write=False|True, ...)`. Default cursors are binary; use `conn.cursor(row_factory=dict_row)` for dict rows. Direct database access via `psql "$POSTGRES_URL"` is available for investigation and debugging.
- SQL safety: never build SQL with f‑strings/concat. Use `psycopg.sql.SQL`/`Identifier` for dynamic pieces and pass parameters (`%s`/`%(name)s`). Examples: `app/services/note_service.py`, `app/queries/note_comment_query.py`.
- Form feedback: return OpenAPI‑compatible `detail` using `StandardFeedback` (see Standard Components). StandardForm consumes this shape for field tooltips and form‑level alerts. Use `StandardFeedback.raise_error(field, message)` for validation failures.
- Errors:
  - `raise_for` (`app/lib/exceptions_context`): business/domain failures (not found, insufficient scopes). Often localized, maps to HTTP semantics.
  - `HTTPException(status.HTTP_4XX, 'message')`: low‑level/technical errors not worth localizing (e.g., malformed cryptographic data).
- Translation (server): work inside `translation_context(...)` (middleware sets this) and call `t()/nt()` from `app/lib/translation.py`.
- Rendering: use `app/lib/render_response.py` to return HTML; it applies standard layout, config, and localization so the frontend can just call i18next.
- Jinja loader: `render_jinja`/`include` auto‑append `.html.jinja`. Refer to templates without the suffix (e.g., `extends '_base'`).
- HTTP clients: use `app/utils.py:HTTP` (SSRF‑protected) for external calls; `HTTP_INTERNAL` for trusted internal calls.
- Context helpers: prefer `get_request()`, `auth_user()`, `auth_scopes()` instead of passing the Request or auth state through call chains.
- Concurrency: use `TaskGroup` for fan‑out/fan‑in I/O; let unexpected states raise (don’t swallow). See usage in controllers and services.
- Auditing & rate limits: record important actions via `audit(...)` (e.g., rate‑limit updates) and gate heavy endpoints with `@rate_limit` middleware hooks (`app/middlewares/rate_limit_middleware.py`).
- Geometry writes: follow existing usage of `ST_QuantizeCoordinates(..., 7)` when inserting/updating geometries to keep storage and comparisons stable.
- Auth dependencies: protect web pages with `web_user(...)` and API endpoints with `api_user(...)` (see `app/lib/auth_context.py`); use role scopes like `'role_moderator'`/`'role_administrator'` where needed. For data visibility in queries, reuse utilities like `user_is_moderator(user)`.

## Frontend Conventions

- Single‑bundle strategy:
  - JavaScript: `app/views/main.ts` is the single deferred entry that imports feature modules. Each module guards itself with a page/body marker so it only runs where applicable. Prefer adding new behavior here instead of creating new page‑specific entries.
  - CSS: `app/views/main.scss` imports all Bootstrap, shared, and feature styles. Prefer adding partials and importing them into `main.scss` rather than per‑page styles. This improves cache efficiency and compression across the site.
  - Exceptions: create a separate entry only for hard isolation (e.g., editor iframes like `id.ts`/`rapid.ts`, or `embed.ts`). Declare it in `vite.config.ts` and include it via `vite_render_asset` from a dedicated template.
- Synchronous bootstrap: `app/views/main-sync.ts` is the only blocking script; keep it import‑free to avoid extra polyfills and ensure theme setup before paint.
- TypeScript: `tsconfig.json` has `"strict": true`. Prefer fail‑fast crashes over silently continuing with unexpected states. Avoid defensive optional chaining (`?.`) or fallback operators (`??`) on values guaranteed by template or control flow—these hide bugs instead of surfacing them. Omit explicit return types when inferable; redundant annotations add noise and slow iteration.
- DOM typing: rely on `typed-query-selector` inference for `querySelector/All`; avoid explicit generics (`querySelector<HTML...>`) and `as HTML...` casts.
- Modern syntax: write ES2023/modern CSS. Polyfills and transforms are injected automatically (Vite legacy plugin in `vite.config.ts`, Babel preset‑env + `core-js` and `browserslist` in `package.json`, Autoprefixer in `vite.config.ts`).
- Styling: SCSS with Bootstrap 5. Prefer semantic classes; avoid inline styles; use `rem`/`em` instead of `px` where sensible.
- Router integration: for map/index pages, implement `IndexController` and register routes via `configureRouter(...)` (`app/views/index/router.ts`); navigate with `routerNavigateStrict(...)`.
- Forms: use `app/views/lib/standard-form.ts` for submissions and feedback (see Standard Components); avoid bespoke AJAX.
- Jinja templates:
  - General page templates extend `_base` (omit the `.html.jinja` suffix when referring to templates); shared markup lives either next to the feature under a leading-underscore filename (e.g. `traces/_list-entry`) or globally in `app/views/lib/`.
  - Build reusable fragments as includes and avoid macros entirely.
  - When an include needs parameters, set them immediately beforehand and prefix each variable with the component name to avoid collisions (e.g. `multi_input_name`, `entry_hide_preview`). Only add fallbacks inside the partial when the component truly benefits from a default; otherwise let missing data fail loudly.
  - Locals created with `set` should start with an underscore (e.g. `{% set _is_deleted = ... %}`) to avoid clashing with request or component variables.
  - Keep component contexts lean: pass in presentation-ready values.
  - Asset naming: when a Jinja template has a `_` prefix (e.g., `_list-entry.html.jinja`), related TypeScript and SCSS files must use the same prefix (e.g., `_list-entry.ts`, `_list-entry.scss`). This enables IDE file folding to group related files together.

## Standard Components

- StandardForm (client): `configureStandardForm(form, onSuccess, options)` wires Bootstrap validation, handles pending state, posts via fetch, maps backend `detail` into field tooltips or a form alert, and integrates client‑side password hashing. Use it for all interactive forms (examples across `app/views/**`).
- StandardFeedback (server): build JSON responses that StandardForm understands using `StandardFeedback`. For simple success/info messages, return `StandardFeedback.success_result(None, '...')`/`info_result(...)`; for validation failures, call `StandardFeedback.raise_error(field, '...')`.
- StandardPagination (client + server): use `configureStandardPagination(container, opts)` to drive list/table pagination.
  - Markup: a render container (`ul.list-unstyled` or `tbody`) and a trailing `ul.pagination` with `data-action="/api/..."`.
  - Target scoping: pass a container that includes any counters you want updated (e.g. header `[data-sp-num-items]`); `configureStandardPagination` scopes pagination UI + render area internally around the action pagination.
  - Fragment metadata: if a paginated response needs to carry extra per-page data for JS, emit it as a hidden element inside the render container and consume/remove it in `loadCallback`. Select the meta node via class/hierarchy; store values in `data-*`.
  - Requests: browser POSTs a raw `StandardPaginationState` protobuf body (`application/x-protobuf`) with `requested_page` set; the server loads that page using anchors from `current_page`, clears `requested_page`, and returns the updated state in the `X-StandardPagination` response header (base64url‑encoded).
  - Backend helpers: `app/lib/standard_pagination.py` (common SQL, query planning, limited counting, header encoding). For the common “table + WHERE” case, use `sp_paginate_table(...)`.
- Rule of thumb: for interactive form flows, prefer `StandardFeedback` for success/info/errors; reserve `raise_for` for exceptional conditions that should abort the flow entirely (e.g., unauthorized, not found).

## Localization Workflow (frontend + backend)

- Authoring: add English source strings in `config/locale/extra_en.yaml`. Keys must be slug‑like and highly descriptive so they read well at call sites. Example: `password_strength.suggestions.use_at_least_min_length_characters`.
- Frontend usage: always call `i18next.t("literal.key")` (or `t("literal.key")`) with literal string keys next to the call. The i18next pipeline discovers keys via regex and prunes unused ones; dynamic construction is not detected and will be dropped.
- Dynamic exceptions: if a dynamic family of keys is unavoidable, add a static prefix to `scripts/locale_make_i18next.py:_INCLUDE_PREFIXES`.
- Pipeline: `locale-pipeline` runs post‑processing and emits both i18next hashed bundles (`config/locale/i18next`) and GNU gettext catalogs. Files are injected by `map_i18next_files(...)` and bootstrapped in the browser by `app/views/lib/i18n.ts`.
- Backend translation: use `t()/nt()` inside the active translation context; templates get the locale via `render_jinja`/`render_response`.
- Internal admin/moderation UIs: page‑specific admin text is intentionally not localized to speed up iteration and reduce maintenance. Where identical phrasing already exists elsewhere, prefer reusing those locale keys instead of duplicating strings. If an internal string becomes user‑facing later, migrate it to a locale key in the same change.
- Locales hygiene: only add strings that are actually rendered; prefer reusing existing namespaces/keys over introducing near-duplicates.

## Code Generation & Assets

- Protobuf: `proto-pipeline` generates Python stubs in `app/models/proto` and TypeScript clients in `app/views/lib/proto`. Never edit generated files.
- Vite build: `vite-build` outputs hashed JS/CSS to `app/static/vite` and updates the manifest consumed by `vite_render_asset`.
- Precompressed static files: large assets are served via `PrecompressedStaticFiles`; use `static-precompress` to create `.zst`/`.br` siblings instead of committing duplicates.

## Tests & Fixtures

- Tests mirror the app layout (`tests/controllers`, `tests/services`, etc.).
- Shared fixtures live in `tests/conftest.py` and `tests/data/`; prefer extending these over custom per‑test setups.
- Tests rely on background services (Postgres, Mailpit). Starting services (`dev-start`) is a human‑only action unless explicitly allowed. If services aren't running and you don't have permission to start them, treat tests as temporarily unavailable and continue with other checks.
- Test patterns: use AAA (Arrange, Act, Assert) for simple tests. Multi-stage tests use stage comments instead of repeated AAA blocks. Test names must be clear and descriptive; only use docstrings when complexity demands it. Uniformity and glance-through readability are paramount.

## Handy References (copy patterns from these)

- DB helper and connection modes: `app/db.py:137`
- SQL composition examples: `app/services/note_service.py`, `app/queries/note_comment_query.py`
- HTML rendering glue: `app/lib/render_response.py`, `app/lib/render_jinja.py`
- Frontend config and i18n bootstrap: `app/views/lib/config.ts`, `app/views/lib/i18n.ts`
- Frontend entry points: `app/views/main.ts`, `app/views/main-sync.ts`
- Build & polyfills: `vite.config.ts`, `package.json:babel`, `package.json:browserslist`, `tsconfig.json`
- Localization tooling: `config/locale/extra_en.yaml`, `scripts/locale_postprocess.py`, `scripts/locale_make_i18next.py`

When introducing new code, first search for an existing helper or pattern and extend it. Consistency keeps patches lean, predictable, and easy to review.

**Please treat the AGENTS.md guide as living documentation**: if a change in your patch invalidates any section, update the relevant text in the same patch. Likewise, fix anything you notice is incorrect, and add new recurring patterns or contributor-critical guidance as they emerge so newcomers always land on accurate, essential information.
