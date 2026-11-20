# Software directory checks

The catalog and four-way filter are in `app/lib/software_directory.py`. The real
FastAPI router validates query values, and the actual Jinja template renders the
GET form and results. No new RPC or generated protobuf artifacts are needed.

```sh
uv run --no-project --python 3.14 --with fastapi==0.136.1 --with httpx --with jinja2 --with pyyaml python tests/views/software/probe.py
```

This runs five unittest cases (including combination subcases), verifies real
static PNG responses, query validation, selected values, empty states, and the
navbar source link. The only application boundary replaced is the config/auth
dependent `render_response` shell: it renders the actual software template using
Jinja autoescape and the raw English strings, rather than initializing the
application's database, auth context, Vite and gettext environment. Full `_base`,
navbar mounting, generated locales, CSP middleware and Nix services are not
validated by this probe. The standalone shell supplies Bootstrap CSS.

For actual browser GET-form navigation with JavaScript disabled:

```sh
uv run --no-project --python 3.14 --with fastapi==0.136.1 --with httpx --with jinja2 --with pyyaml python tests/views/software/probe.py --serve
# Set SOFTWARE_URL to the printed loopback URL, then:
bun test tests/views/software/browser.test.ts
```

Playwright and Chrome must be installed; `PLAYWRIGHT_PACKAGE` can reference an
existing module. Optional `SOFTWARE_SCREENSHOTS` is a screenshot filename prefix.
Stop the probe server after testing. The two browser cases cover desktop/mobile
layouts, four successful image decodes, combined filters, selected values after
refresh, a no-match state and reset. These are not duplicate backend test cases.

The initial catalog is deliberately four verified active open-source projects
across three categories, not an exhaustive inventory. Proprietary and inactive
filters currently produce an empty result. Metadata requires periodic human
curation, and code licenses do not describe map-data/service-plan licensing.
