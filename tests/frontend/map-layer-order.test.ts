import { beforeEach, expect, mock, test } from "bun:test"
import type { LayerSpecification, Map as MaplibreMap } from "maplibre-gl"

mock.module("@map/vector-styles/liberty.json", () => ({ default: {} }))
mock.module("@runtime/theme", () => ({ effectiveTheme: { value: "light" } }))
mock.module("@utils/local-storage", () => ({
  overlayOpacityStorage: () => ({ value: 1 }),
}))
mock.module("@preact/signals", () => ({
  batch: (callback: () => void) => callback(),
  effect: (callback: () => void) => callback(),
  signal: (value: unknown) => ({ value }),
}))
mock.module("@std/cache/memoize", () => ({ memoize: (callback: unknown) => callback }))
mock.module("@std/collections/filter-keys", () => ({ filterKeys: () => ({}) }))
mock.module("i18next", () => ({ t: (key: string) => key }))
mock.module("maplibre-gl", () => ({ RasterTileSource: class {} }))
Object.assign(globalThis, { window: { devicePixelRatio: 1 } })

const {
  addMapLayer,
  removeMapLayer,
  layersConfig,
  LIBERTY_LAYER_ID,
  AERIAL_LAYER_ID,
  GPS_LAYER_ID,
  NOTES_LAYER_ID,
  STANDARD_LAYER_ID,
} = await import("../../app/views/map/layers/layers")

class TestMap {
  layers: LayerSpecification[] = []
  setGlyphs() {}
  setSprite() {}
  getSprite() {
    return []
  }
  addSprite() {}
  getLayersOrder() {
    return this.layers.map(({ id }) => id)
  }
  getLayer(id: string) {
    return this.layers.find((layer) => layer.id === id)
  }
  addLayer(layer: LayerSpecification, before?: string) {
    const index =
      before === undefined
        ? this.layers.length
        : this.layers.findIndex(({ id }) => id === before)
    expect(index).toBeGreaterThanOrEqual(0)
    this.layers.splice(index, 0, layer)
  }
  removeLayer(id: string) {
    this.layers.splice(
      this.layers.findIndex((layer) => layer.id === id),
      1,
    )
  }
}

beforeEach(() => {
  layersConfig.get(LIBERTY_LAYER_ID)!.vectorStyle = {
    version: 8,
    sources: {},
    layers: [
      { id: "land", type: "background" },
      {
        id: "place",
        type: "symbol",
        source: "places",
        layout: { "text-field": "Place" },
      },
      { id: "road", type: "line", source: "roads" },
      {
        id: "road-name",
        type: "symbol",
        source: "roads",
        layout: { "text-field": "Road" },
      },
    ],
  }
  layersConfig.set(NOTES_LAYER_ID, {
    specification: {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    },
    layerTypes: ["symbol"],
    priority: 130,
  })
})

for (const baseFirst of [true, false]) {
  test(`labels stay above aerial and below overlays with baseFirst=${baseFirst}`, () => {
    const map = new TestMap()
    const actualMap = map as unknown as MaplibreMap
    const order = baseFirst
      ? [LIBERTY_LAYER_ID, AERIAL_LAYER_ID]
      : [AERIAL_LAYER_ID, LIBERTY_LAYER_ID]
    addMapLayer(actualMap, GPS_LAYER_ID, false)
    addMapLayer(actualMap, NOTES_LAYER_ID, false)
    for (const id of order) addMapLayer(actualMap, id, false)
    expect(map.getLayersOrder()).toEqual([
      "liberty:land",
      "liberty:road",
      "aerial",
      "liberty:place",
      "liberty:road-name",
      "gps",
      "notes",
    ])
    removeMapLayer(actualMap, AERIAL_LAYER_ID, false)
    addMapLayer(actualMap, AERIAL_LAYER_ID, false)
    expect(map.getLayersOrder().indexOf("aerial")).toBeLessThan(
      map.getLayersOrder().indexOf("liberty:place"),
    )
    removeMapLayer(actualMap, LIBERTY_LAYER_ID, false)
    addMapLayer(actualMap, LIBERTY_LAYER_ID, false)
    expect(map.getLayersOrder()).toEqual([
      "liberty:land",
      "liberty:road",
      "aerial",
      "liberty:place",
      "liberty:road-name",
      "gps",
      "notes",
    ])
  })
}

test("raster basemaps and non-base symbols keep their configured priorities", () => {
  const map = new TestMap()
  const actualMap = map as unknown as MaplibreMap
  addMapLayer(actualMap, NOTES_LAYER_ID, false)
  addMapLayer(actualMap, AERIAL_LAYER_ID, false)
  addMapLayer(actualMap, STANDARD_LAYER_ID, false)
  expect(map.getLayersOrder()).toEqual(["standard", "aerial", "notes"])
})

test("Liberty preserves arrow and bridge ordering while labels remain above toggled aerial", async () => {
  const style = await Bun.file(
    new URL("../../app/views/map/vector-styles/liberty.json", import.meta.url),
  ).json()
  layersConfig.get(LIBERTY_LAYER_ID)!.vectorStyle = style
  const map = new TestMap()
  const actualMap = map as unknown as MaplibreMap
  addMapLayer(actualMap, LIBERTY_LAYER_ID, false)
  const originalOrder = style.layers.map(
    (layer: { id: string }) => `liberty:${layer.id}`,
  )
  expect(map.getLayersOrder()).toEqual(originalOrder)
  for (let i = 0; i < 2; i++) {
    addMapLayer(actualMap, AERIAL_LAYER_ID, false)
    const order = map.getLayersOrder()
    for (const layer of style.layers) {
      const isLabel =
        layer.type === "symbol" && layer.layout?.["text-field"] !== undefined
      if (isLabel) {
        expect(order.indexOf(`liberty:${layer.id}`)).toBeGreaterThan(
          order.indexOf("aerial"),
        )
      } else {
        expect(order.indexOf(`liberty:${layer.id}`)).toBeLessThan(
          order.indexOf("aerial"),
        )
      }
    }
    removeMapLayer(actualMap, AERIAL_LAYER_ID, false)
    expect(map.getLayersOrder()).toEqual(originalOrder)
  }
})
