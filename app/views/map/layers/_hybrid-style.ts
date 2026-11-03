import type { StyleSpecification } from "maplibre-gl"

/** Keep imagery unobscured while retaining roads, boundaries and labels. */
export const createHybridStyle = (liberty: StyleSpecification) => {
  const style = structuredClone(liberty)
  style.layers = style.layers.filter(
    (layer) =>
      layer.type === "symbol" ||
      (layer.type === "line" &&
        ["transportation", "boundary", "waterway", "aeroway"].includes(
          layer["source-layer"] ?? "",
        )),
  )
  const usedSources = new Set(
    style.layers.flatMap((layer) => ("source" in layer ? [layer.source] : [])),
  )
  for (const id of Object.keys(style.sources)) {
    if (!usedSources.has(id)) delete style.sources[id]
  }
  style.sources.imagery = {
    type: "raster",
    tiles: [
      "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    tileSize: 256,
    maxzoom: 23,
  }
  style.layers.unshift({
    id: "imagery",
    type: "raster",
    source: "imagery",
    paint: { "raster-opacity": 1 },
  })
  return style
}
