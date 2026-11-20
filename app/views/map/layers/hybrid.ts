import type { RasterSourceSpecification, StyleSpecification } from "maplibre-gl"

const LINE_SOURCES = new Set(["transportation", "waterway", "boundary", "aeroway"])

/** Keep navigation features above imagery without obscuring it with land fills. */
export const createHybridStyle = (
  base: StyleSpecification,
  imagery: RasterSourceSpecification,
): StyleSpecification => {
  const layers = base.layers.filter(
    (layer) =>
      layer.type === "symbol" ||
      (layer.type === "line" && LINE_SOURCES.has(layer["source-layer"] ?? "")),
  )
  const sources: StyleSpecification["sources"] = {}
  for (const layer of layers) {
    if ("source" in layer && typeof layer.source === "string") {
      sources[layer.source] = { ...base.sources[layer.source]! }
    }
  }
  sources["hybrid-imagery"] = { ...imagery }

  return {
    ...base,
    sources,
    layers: [
      {
        id: "hybrid-imagery",
        type: "raster",
        source: "hybrid-imagery",
        paint: { "raster-opacity": 1 },
      },
      ...layers,
    ],
  }
}
