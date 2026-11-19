import { signal } from "@preact/signals"
import { describe, expect, mock, test } from "bun:test"
import type { Map as MaplibreMap, StyleSpecification } from "maplibre-gl"
import { createRequire } from "node:module"
import { hybridStyle } from "../../app/views/map/vector-styles/hybrid"
import liberty from "../../app/views/map/vector-styles/liberty.json"

const requireMap = createRequire(import.meta.resolve("maplibre-gl"))
const { validateStyleMin } = requireMap("@maplibre/maplibre-gl-style-spec")

mock.module("@runtime/theme", () => ({ effectiveTheme: signal("light") }))
mock.module("@utils/local-storage", () => ({
  overlayOpacityStorage: () => signal(0.25),
}))
mock.module("i18next", () => ({ t: (key: string) => key }))
mock.module("maplibre-gl", () => ({ RasterTileSource: class {} }))
Object.assign(globalThis, { window: { devicePixelRatio: 1 } })

const {
  addMapLayer,
  addMapLayerSources,
  removeMapLayer,
  hasMapLayer,
  layersConfig,
  HYBRID_LAYER_ID,
  AERIAL_LAYER_ID,
  GPS_LAYER_ID,
  LIBERTY_LAYER_ID,
  resolveLayerCodeOrId,
} = await import("../../app/views/map/layers/layers")

class MapFixture {
  sources = new Map<string, any>()
  layers: any[] = []
  glyphs: string | null = null
  sprites: { id: string; url: string }[] = []
  addSource(id: string, spec: any) {
    if (this.sources.has(id)) throw new Error(`duplicate source ${id}`)
    this.sources.set(id, structuredClone(spec))
  }
  getSource(id: string) {
    return this.sources.get(id)
  }
  getLayersOrder() {
    return this.layers.map((l) => l.id)
  }
  addLayer(layer: any, before?: string) {
    if (this.layers.some((l) => l.id === layer.id))
      throw new Error(`duplicate layer ${layer.id}`)
    if (layer.source && !this.sources.has(layer.source))
      throw new Error(`missing source ${layer.source}`)
    const index =
      before === undefined
        ? this.layers.length
        : this.layers.findIndex((l) => l.id === before)
    if (index < 0) throw new Error(`missing before ${before}`)
    this.layers.splice(index, 0, structuredClone(layer))
  }
  removeLayer(id: string) {
    this.layers = this.layers.filter((l) => l.id !== id)
  }
  setGlyphs(value: string | null) {
    this.glyphs = value
  }
  getSprite() {
    return this.sprites
  }
  setSprite(url: string | null) {
    this.sprites = url ? [{ id: "default", url }] : []
  }
  addSprite(id: string, url: string) {
    this.sprites.push({ id, url })
  }
  removeSprite(id: string) {
    this.sprites = this.sprites.filter((s) => s.id !== id)
  }
  asMap() {
    return this as unknown as MaplibreMap
  }
  style(): StyleSpecification {
    return {
      version: 8,
      sources: Object.fromEntries(this.sources),
      layers: this.layers,
      ...(this.glyphs ? { glyphs: this.glyphs } : {}),
      ...(this.sprites.length ? { sprite: this.sprites } : {}),
    }
  }
}

describe("hybrid aerial", () => {
  test("valid complete style retains roads and POIs above fully opaque imagery", () => {
    const original = structuredClone(liberty)
    const style = hybridStyle(liberty as StyleSpecification, {
      type: "raster",
      tiles: ["https://example.org/{z}/{x}/{y}.png"],
      tileSize: 256,
    })
    expect(validateStyleMin(style)).toEqual([])
    expect(style.layers[0]).toMatchObject({
      type: "raster",
      paint: { "raster-opacity": 1 },
    })
    expect(style.layers.some((l) => l.id === "road_motorway")).toBe(true)
    expect(style.layers.some((l) => l.id === "poi_r1")).toBe(true)
    expect(
      style.layers.some(
        (l) =>
          l.type === "fill" || l.type === "fill-extrusion" || l.type === "background",
      ),
    ).toBe(false)
    expect(
      style.layers.some((l) => l.id === "park_outline" || l.id === "waterway_river"),
    ).toBe(false)
    expect(liberty).toEqual(original)
    for (const [id, source] of Object.entries(style.sources)) {
      if (id in liberty.sources)
        expect(source).not.toBe(liberty.sources[id as keyof typeof liberty.sources])
    }
  })

  test("all restore orders keep imagery/annotations together below GPS", () => {
    const ids = [HYBRID_LAYER_ID, AERIAL_LAYER_ID, GPS_LAYER_ID]
    for (const a of ids)
      for (const b of ids.filter((id) => id !== a)) {
        const c = ids.find((id) => id !== a && id !== b)!
        const map = new MapFixture()
        addMapLayerSources(map.asMap(), "all")
        for (const id of [a, b, c]) addMapLayer(map.asMap(), id, false)
        expect(validateStyleMin(map.style())).toEqual([])
        const order = map.getLayersOrder()
        const hybrid = order.filter((id) => id.startsWith("hybrid:"))
        expect(order.indexOf(AERIAL_LAYER_ID)).toBeLessThan(order.indexOf(hybrid[0]!))
        expect(order.indexOf(hybrid.at(-1)!)).toBeLessThan(order.indexOf(GPS_LAYER_ID))
        expect(
          map.layers.find((l) => l.id === "hybrid:imagery").paint["raster-opacity"],
        ).toBe(1)
        expect(
          map.layers.find((l) => l.id === AERIAL_LAYER_ID).paint["raster-opacity"],
        ).toBe(0.25)
        removeMapLayer(map.asMap(), HYBRID_LAYER_ID, false)
        expect(map.getLayersOrder()).toEqual([AERIAL_LAYER_ID, GPS_LAYER_ID])
        expect(hasMapLayer(map.asMap(), HYBRID_LAYER_ID)).toBe(false)
        addMapLayer(map.asMap(), HYBRID_LAYER_ID, false)
        expect(validateStyleMin(map.style())).toEqual([])
      }
  })

  test("exact minimap sources, URL code, attribution and Liberty isolation", () => {
    const original = structuredClone(layersConfig.get(LIBERTY_LAYER_ID)!.vectorStyle)
    const map = new MapFixture()
    addMapLayerSources(map.asMap(), HYBRID_LAYER_ID)
    addMapLayer(map.asMap(), HYBRID_LAYER_ID, false)
    expect(resolveLayerCodeOrId("I" as any)).toBe(HYBRID_LAYER_ID)
    expect(resolveLayerCodeOrId(HYBRID_LAYER_ID)).toBe(HYBRID_LAYER_ID)
    expect([...map.sources.keys()].every((id) => id.startsWith("hybrid:"))).toBe(true)
    expect(map.sources.get("hybrid:imagery").attribution).toContain("Esri")
    expect(map.sources.get("hybrid:imagery").attribution).toContain("/copyright")
    expect(layersConfig.get(LIBERTY_LAYER_ID)!.vectorStyle).toEqual(original)
    expect(validateStyleMin(map.style())).toEqual([])
    removeMapLayer(map.asMap(), HYBRID_LAYER_ID, false)
    expect(map.layers).toEqual([])
    expect(map.glyphs).toBeNull()
    expect(map.sprites).toEqual([])
    addMapLayer(map.asMap(), HYBRID_LAYER_ID, false)
    expect(validateStyleMin(map.style())).toEqual([])
  })
})
