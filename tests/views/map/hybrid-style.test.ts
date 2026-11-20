import { expect, test } from "bun:test"
import { createHybridStyle } from "../../../app/views/map/layers/hybrid-style"
import liberty from "../../../app/views/map/vector-styles/liberty.json"
import type { StyleSpecification } from "maplibre-gl"

const aerial = {
  type: "raster" as const,
  tileSize: 256,
  tiles: ["https://example.invalid/{z}/{x}/{y}.png"],
  attribution: "Imagery provider",
}
const original = liberty as unknown as StyleSpecification

test("hybrid excludes opaque fills while preserving road, label and POI ordering", () => {
  const hybrid = createHybridStyle(original, aerial)
  expect(hybrid.layers[0]).toEqual({
    id: "hybrid-aerial",
    type: "raster",
    source: "hybrid-aerial",
    paint: { "raster-opacity": 1 },
  })
  expect(hybrid.layers.slice(1)).toEqual(
    original.layers.filter((layer) =>
      ["line", "symbol", "circle"].includes(layer.type),
    ),
  )
  expect(
    hybrid.layers.some((layer) =>
      ["fill", "fill-extrusion", "background"].includes(layer.type),
    ),
  ).toBe(false)
  expect(hybrid.glyphs).toBe(original.glyphs)
  expect(hybrid.sprite).toEqual(original.sprite)
})

test("hybrid construction and source edits do not mutate Liberty or the aerial overlay", () => {
  const snapshot = structuredClone(original)
  const hybrid = createHybridStyle(original, aerial)
  hybrid.sources["hybrid-aerial"]!.attribution = "changed"
  hybrid.sources["openmaptiles"]!.attribution = "changed"
  expect(original).toEqual(snapshot)
  expect(aerial.attribution).toBe("Imagery provider")
  expect(hybrid.sources["hybrid-aerial"]).not.toBe(aerial)
})
