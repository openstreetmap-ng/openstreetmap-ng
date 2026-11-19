import type { RasterSourceSpecification, StyleSpecification } from "maplibre-gl"

/** Keep the aerial image unobstructed by Liberty's terrain and area paints. */
export const hybridStyle = (
  liberty: StyleSpecification,
  imagery: RasterSourceSpecification,
): StyleSpecification => {
  const annotations = liberty.layers.filter(
    (layer) =>
      layer.type === "symbol" ||
      (layer.type === "line" &&
        ["transportation", "aeroway", "boundary"].includes(
          layer["source-layer"] ?? "",
        )),
  )
  const sourceIds = new Set(
    annotations.flatMap((layer) => ("source" in layer ? [layer.source] : [])),
  )
  return {
    ...liberty,
    name: "Hybrid aerial",
    sources: {
      ...Object.fromEntries(
        Object.entries(liberty.sources)
          .filter(([id]) => sourceIds.has(id))
          .map(([id, source]) => [id, { ...source }]),
      ),
      imagery: { ...imagery },
    },
    layers: [
      {
        id: "imagery",
        type: "raster",
        source: "imagery",
        paint: { "raster-opacity": 1 },
      },
      ...annotations,
    ],
  }
}
