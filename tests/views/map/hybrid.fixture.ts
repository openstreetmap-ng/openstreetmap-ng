import type { LayerCode, LayerId } from "@map/layers/layers"
import { init } from "i18next"
import { Map as GLMap } from "maplibre-gl"

await init({
  lng: "en",
  resources: {
    en: {
      translation: {
        javascripts: {
          map: {
            openstreetmap_contributors: "OpenStreetMap contributors",
            website_and_api_terms: "Website and API terms",
          },
        },
      },
    },
  },
})
const layers = await import("@map/layers/layers")
const hybridId = "hybrid" as LayerId
const hybrid = layers.layersConfig.get(hybridId)
const errors: string[] = []
let map: GLMap | undefined

const ready = async () => {
  if (!hybrid) return
  map = new GLMap({
    container: "map",
    center: [-0.1276, 51.5072],
    zoom: 14,
    style: { version: 8, sources: {}, layers: [] },
    canvasContextAttributes: { preserveDrawingBuffer: true },
    attributionControl: true,
  })
  map.on("error", (event) => errors.push(event.error.message))
  await map.once("load")
  layers.addMapLayerSources(map, hybridId)
  layers.addMapLayerSources(map, layers.LIBERTY_LAYER_ID)
  layers.addMapLayer(map, hybridId)
  await map.once("idle")
}

Object.assign(window, {
  hybridTest: {
    exists: Boolean(hybrid?.isBaseLayer),
    ready: ready(),
    errors,
    config: hybrid,
    lookup: () => layers.resolveLayerCodeOrId("B" as LayerCode),
    snapshot: () => ({
      layers: map!.getStyle().layers,
      features: map!.queryRenderedFeatures().length,
      active: layers.activeBaseLayerId.value,
      center: map!.getCenter().toArray(),
    }),
    switch: async (id: string) => {
      layers.removeMapLayer(map!, layers.activeBaseLayerId.peek()!)
      layers.addMapLayer(map!, id as LayerId)
      await map!.once("idle")
    },
    resize: () => map!.resize(),
    pan: async () => {
      map!.panBy([80, 0], { duration: 0 })
      await map!.once("idle")
    },
  },
})
