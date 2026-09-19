import { afterAll, describe, expect, mock, test } from "bun:test"
import type { Map as MaplibreMap, LayerSpecification } from "maplibre-gl"

// Keep map ordering real to this module; no browser, tiles or theme bootstrap.
const originalWindow = globalThis.window
Object.defineProperty(globalThis, "window", {
  configurable: true,
  value: { devicePixelRatio: 1 },
})
mock.module("@preact/signals", () => ({
  batch: (fn: () => void) => fn(),
  effect: () => {},
  signal: (value: unknown) => ({ value }),
}))
mock.module("@runtime/theme", () => ({ effectiveTheme: { value: "light" } }))
mock.module("@std/cache/memoize", () => ({ memoize: (fn: unknown) => fn }))
mock.module("@std/collections/filter-keys", () => ({
  filterKeys: (
    obj: Record<string, unknown>,
    accept: (key: string) => boolean,
  ) => Object.fromEntries(Object.entries(obj).filter(([key]) => accept(key))),
}))
mock.module("@utils/local-storage", () => ({
  overlayOpacityStorage: () => ({ value: 1 }),
}))
mock.module("i18next", () => ({ t: (key: string) => key }))
mock.module("maplibre-gl", () => ({ RasterTileSource: class {} }))

const {
  addMapLayer,
  removeMapLayer,
  layersConfig,
  LIBERTY_LAYER_ID,
  AERIAL_LAYER_ID,
  GPS_LAYER_ID,
  STANDARD_LAYER_ID,
} = await import("../../app/views/map/layers/layers")

afterAll(() => {
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: originalWindow,
  })
  mock.restore()
})

class OrderingMap {
  layers: LayerSpecification[] = []
  getLayersOrder() {
    return this.layers.map((layer) => layer.id)
  }
  getLayer(id: string) {
    const layer = this.layers.find((layer) => layer.id === id)!
    return {
      ...layer,
      sourceLayer: "source-layer" in layer ? layer["source-layer"] : undefined,
    }
  }
  addLayer(layer: LayerSpecification, before?: string) {
    expect(this.getLayersOrder()).not.toContain(layer.id)
    const index =
      before === undefined
        ? this.layers.length
        : this.layers.findIndex((item) => item.id === before)
    expect(index).toBeGreaterThanOrEqual(0)
    this.layers.splice(index, 0, layer)
  }
  removeLayer(id: string) {
    this.layers = this.layers.filter((layer) => layer.id !== id)
  }
  setGlyphs() {}
  getSprite() {
    return []
  }
  setSprite() {}
  addSprite() {}
  removeSprite() {}
  asMap() {
    return this as unknown as MaplibreMap
  }
}

const style = layersConfig.get(LIBERTY_LAYER_ID)!.vectorStyle!
const places = style.layers.filter(
  (layer) => layer.type === "symbol" && layer["source-layer"] === "place",
)
const expectedBaseOrder = style.layers.map((layer) => `liberty:${layer.id}`)
const verifyOverlayOrder = (map: OrderingMap) => {
  const order = map.getLayersOrder()
  const aerial = order.indexOf(AERIAL_LAYER_ID)
  const gps = order.indexOf(GPS_LAYER_ID)
  expect(places.length).toBeGreaterThan(0)
  for (const layer of places) {
    const position = order.indexOf(`liberty:${layer.id}`)
    expect(position).toBeGreaterThan(aerial)
    if (gps !== -1) expect(position).toBeLessThan(gps)
  }
  for (const layer of style.layers.filter((layer) => !places.includes(layer))) {
    expect(order.indexOf(`liberty:${layer.id}`)).toBeLessThan(aerial)
  }
  expect(order.filter((id) => id.startsWith("liberty:"))).toEqual(
    expectedBaseOrder,
  )
  expect(
    map.layers.find((layer) => layer.id === AERIAL_LAYER_ID)?.paint,
  ).toMatchObject({
    "raster-opacity": 1,
  })
}

describe("place labels above opaque aerial imagery", () => {
  const orders = [
    [LIBERTY_LAYER_ID, AERIAL_LAYER_ID, GPS_LAYER_ID],
    [LIBERTY_LAYER_ID, GPS_LAYER_ID, AERIAL_LAYER_ID],
    [AERIAL_LAYER_ID, LIBERTY_LAYER_ID, GPS_LAYER_ID],
    [AERIAL_LAYER_ID, GPS_LAYER_ID, LIBERTY_LAYER_ID],
    [GPS_LAYER_ID, AERIAL_LAYER_ID, LIBERTY_LAYER_ID],
    [GPS_LAYER_ID, LIBERTY_LAYER_ID, AERIAL_LAYER_ID],
  ]
  for (const order of orders) {
    test(`insertion order ${order.join(", ")}`, () => {
      const map = new OrderingMap()
      for (const id of order) addMapLayer(map.asMap(), id, false)
      verifyOverlayOrder(map)
    })
  }
  test("base-only style keeps its exact order, including road arrows below bridges", () => {
    const map = new OrderingMap()
    addMapLayer(map.asMap(), LIBERTY_LAYER_ID, false)
    expect(map.getLayersOrder()).toEqual(expectedBaseOrder)
  })
  test("removing and restoring aerial keeps base order and labels visible", () => {
    const map = new OrderingMap()
    addMapLayer(map.asMap(), LIBERTY_LAYER_ID, false)
    addMapLayer(map.asMap(), AERIAL_LAYER_ID, false)
    removeMapLayer(map.asMap(), AERIAL_LAYER_ID, false)
    expect(map.getLayersOrder()).toEqual(expectedBaseOrder)
    addMapLayer(map.asMap(), AERIAL_LAYER_ID, false)
    verifyOverlayOrder(map)
  })
  test("switching raster to vector under existing overlays inserts labels above aerial", () => {
    const map = new OrderingMap()
    addMapLayer(map.asMap(), STANDARD_LAYER_ID, false)
    addMapLayer(map.asMap(), GPS_LAYER_ID, false)
    addMapLayer(map.asMap(), AERIAL_LAYER_ID, false)
    removeMapLayer(map.asMap(), STANDARD_LAYER_ID, false)
    addMapLayer(map.asMap(), LIBERTY_LAYER_ID, false)
    verifyOverlayOrder(map)
  })
  test("switching back to raster leaves no vector labels and preserves overlay order", () => {
    const map = new OrderingMap()
    addMapLayer(map.asMap(), LIBERTY_LAYER_ID, false)
    addMapLayer(map.asMap(), AERIAL_LAYER_ID, false)
    addMapLayer(map.asMap(), GPS_LAYER_ID, false)
    removeMapLayer(map.asMap(), LIBERTY_LAYER_ID, false)
    addMapLayer(map.asMap(), STANDARD_LAYER_ID, false)
    expect(map.getLayersOrder()).toEqual([
      STANDARD_LAYER_ID,
      AERIAL_LAYER_ID,
      GPS_LAYER_ID,
    ])
  })
})
