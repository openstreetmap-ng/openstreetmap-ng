import { afterAll, describe, expect, mock, test } from "bun:test"
import type {
  LayerSpecification,
  Map as MaplibreMap,
  SourceSpecification,
} from "maplibre-gl"
import liberty from "../../app/views/map/vector-styles/liberty.json"

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
  filterKeys: (obj: Record<string, unknown>, accept: (key: string) => boolean) =>
    Object.fromEntries(Object.entries(obj).filter(([key]) => accept(key))),
}))
mock.module("@utils/local-storage", () => ({
  // Hybrid imagery must stay opaque even if the user saved 25% for the overlay.
  overlayOpacityStorage: () => ({ value: 0.25 }),
}))
mock.module("i18next", () => ({ t: (key: string) => key }))
mock.module("maplibre-gl", () => ({ RasterTileSource: class {} }))

const {
  addMapLayer,
  addMapLayerSources,
  addLayerEventHandler,
  removeMapLayer,
  resolveLayerCodeOrId,
  hasMapLayer,
  layersConfig,
  LIBERTY_LAYER_ID,
  HYBRID_LAYER_ID,
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

// Exercise the production layer manager without a browser, WebGL or tile requests.
class TestMap {
  layers: LayerSpecification[] = []
  sources = new Map<string, SourceSpecification>()
  getLayersOrder() {
    return this.layers.map((layer) => layer.id)
  }
  addSource(id: string, source: SourceSpecification) {
    expect(this.sources.has(id)).toBe(false)
    this.sources.set(id, source)
  }
  addLayer(layer: LayerSpecification, before?: string) {
    expect(this.getLayersOrder()).not.toContain(layer.id)
    if ("source" in layer && typeof layer.source === "string") {
      expect(this.sources.has(layer.source)).toBe(true)
    }
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

const style = layersConfig.get(HYBRID_LAYER_ID)!.vectorStyle!
const newMap = () => {
  const map = new TestMap()
  addMapLayerSources(map.asMap(), "all")
  return map
}

describe("hybrid aerial", () => {
  test("opaque imagery is below roads, POIs and names, without land or building fills", () => {
    expect(style.layers[0]).toMatchObject({
      type: "raster",
      paint: { "raster-opacity": 1 },
    })
    expect(style.layers.filter((layer) => layer.type === "raster")).toHaveLength(1)
    for (const layer of style.layers.slice(1)) {
      expect(["line", "symbol"]).toContain(layer.type)
      expect(["landuse", "landcover", "park", "building"]).not.toContain(
        "source-layer" in layer ? layer["source-layer"] : undefined,
      )
    }
    for (const id of [
      "road_motorway",
      "bridge_motorway",
      "poi_r1",
      "label_city",
      "highway-name-major",
    ]) {
      expect(style.layers.findIndex((layer) => layer.id === id)).toBeGreaterThan(0)
    }
    // Keep Liberty's relative ordering, including arrows before bridge casing.
    const retained = new Set(style.layers.slice(1).map((layer) => layer.id))
    expect(style.layers.slice(1)).toEqual(
      liberty.layers.filter((layer) => retained.has(layer.id)),
    )
    expect(style.glyphs).toBe(liberty.glyphs)
    expect(style.sprite).toEqual(liberty.sprite)
    expect(style.sources).not.toHaveProperty("ne2_shaded")
  })

  test("source credits survive main-map and minimap creation without changing either style", () => {
    const original = JSON.stringify(liberty)
    const hybrid = JSON.stringify(style)
    for (let i = 0; i < 2; i++) {
      const map = new TestMap()
      addMapLayerSources(map.asMap(), HYBRID_LAYER_ID)
      addMapLayer(map.asMap(), HYBRID_LAYER_ID, false)
      expect(map.sources.get("hybrid:hybrid-imagery")).toMatchObject({
        type: "raster",
        tileSize: 256,
        attribution: "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
      })
      expect(map.sources.has("hybrid:openmaptiles")).toBe(true)
      expect(map.sources.size).toBe(2)
      expect(map.layers[0]?.paint).toEqual({ "raster-opacity": 1 })
    }
    expect(JSON.stringify(liberty)).toBe(original)
    expect(JSON.stringify(style)).toBe(hybrid)
  })

  test("distinct URL code resolves to a base layer", () => {
    const config = layersConfig.get(HYBRID_LAYER_ID)!
    expect(config.isBaseLayer).toBe(true)
    expect(resolveLayerCodeOrId(config.layerCode!)).toBe(HYBRID_LAYER_ID)
    expect(resolveLayerCodeOrId(HYBRID_LAYER_ID)).toBe(HYBRID_LAYER_ID)
    const codes = [...layersConfig.values()]
      .map((item) => item.layerCode)
      .filter((code) => code !== undefined)
    expect(new Set(codes).size).toBe(codes.length)
  })

  for (const order of [
    [HYBRID_LAYER_ID, AERIAL_LAYER_ID, GPS_LAYER_ID],
    [HYBRID_LAYER_ID, GPS_LAYER_ID, AERIAL_LAYER_ID],
    [AERIAL_LAYER_ID, HYBRID_LAYER_ID, GPS_LAYER_ID],
    [AERIAL_LAYER_ID, GPS_LAYER_ID, HYBRID_LAYER_ID],
    [GPS_LAYER_ID, AERIAL_LAYER_ID, HYBRID_LAYER_ID],
    [GPS_LAYER_ID, HYBRID_LAYER_ID, AERIAL_LAYER_ID],
  ]) {
    test(`hybrid and GPS stay visible in insertion order ${order.join(", ")}`, () => {
      const map = newMap()
      for (const id of order) addMapLayer(map.asMap(), id, false)
      expect(hasMapLayer(map.asMap(), AERIAL_LAYER_ID)).toBe(false)
      expect(map.getLayersOrder()).toEqual([
        ...style.layers.map((layer) => `hybrid:${layer.id}`),
        GPS_LAYER_ID,
      ])
    })
  }

  test("switching from Liberty and aerial removes the redundant overlay and emits its removal", () => {
    const map = newMap()
    addMapLayer(map.asMap(), LIBERTY_LAYER_ID)
    addMapLayer(map.asMap(), AERIAL_LAYER_ID)
    addMapLayer(map.asMap(), GPS_LAYER_ID)
    const removed: string[] = []
    const dispose = addLayerEventHandler((added, id) => {
      if (!added) removed.push(id)
    })
    try {
      removeMapLayer(map.asMap(), LIBERTY_LAYER_ID)
      addMapLayer(map.asMap(), HYBRID_LAYER_ID)
      expect(removed).toEqual([LIBERTY_LAYER_ID, AERIAL_LAYER_ID])
      expect(map.layers[0]?.paint).toEqual({ "raster-opacity": 1 })
      removeMapLayer(map.asMap(), HYBRID_LAYER_ID)
      addMapLayer(map.asMap(), STANDARD_LAYER_ID)
      addMapLayer(map.asMap(), AERIAL_LAYER_ID)
      expect(map.getLayersOrder()).toEqual([
        STANDARD_LAYER_ID,
        AERIAL_LAYER_ID,
        GPS_LAYER_ID,
      ])
      expect(map.layers[1]?.paint).toEqual({ "raster-opacity": 0.25 })
    } finally {
      dispose()
    }
  })
})
