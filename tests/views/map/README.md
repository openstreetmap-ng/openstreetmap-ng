# Hybrid aerial regression

From the repository root:

```sh
bun test tests/views/map/hybrid-style.test.ts tests/views/map/hybrid.test.ts
HYBRID_LIVE_RENDER=1 bun test tests/views/map/hybrid.test.ts
```

Browser checks require Playwright and installed Chrome. `PLAYWRIGHT_PACKAGE`
may point to an external Playwright module entry point. Live rendering uses
the existing public Esri imagery and OpenFreeMap Liberty tile, glyph and sprite
endpoints, without credentials. It requires network access and WebGL support.
Set `HYBRID_SCREENSHOT_DIR` to an existing directory to save desktop and mobile
screenshots. Do not interpret the default registry-only check as a rendering test.

The browser fixture runs the real layer registry, add/remove functions, signals,
MapLibre renderer and Liberty style. Only theme and overlay-opacity storage are
replaced. It checks full-opacity imagery, transparent vector layer selection,
real rendered features, nonuniform canvas pixels, layer-code lookup and switching
to Liberty and back at 1280px and 390px widths. The pure tests verify ordering,
sprites/glyphs and non-mutation of the existing styles and sources.

This is not the complete authenticated application/sidebar or Nix backend test
environment. The sidebar entry and English source translation are included in the
patch; generated locale bundles must be built through the usual project pipeline.
