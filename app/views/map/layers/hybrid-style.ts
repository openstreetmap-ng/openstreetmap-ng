import type { SourceSpecification, StyleSpecification } from "maplibre-gl"

export const createHybridStyle = (
  vectorStyle: StyleSpecification,
  aerialSource: Extract<SourceSpecification, { type: "raster" }>,
) => {
  const style = structuredClone(vectorStyle)
  style.sources["hybrid-aerial"] = structuredClone(aerialSource)
  // Keep roads, labels and POIs without opaque land-use or background fills.
  style.layers = [
    {
      id: "hybrid-aerial",
      type: "raster",
      source: "hybrid-aerial",
      paint: { "raster-opacity": 1 },
    },
    ...style.layers.filter((layer) =>
      ["line", "symbol", "circle"].includes(layer.type),
    ),
  ]
  return style
}
