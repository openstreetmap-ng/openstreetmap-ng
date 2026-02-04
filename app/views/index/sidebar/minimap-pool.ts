import { configureDefaultMapBehavior } from "@lib/map/defaults"
import {
  addMapLayer,
  addMapLayerSources,
  type LayerId,
  layersConfig,
} from "@lib/map/layers/layers"
import { assertExists } from "@std/assert"
import { memoize } from "@std/cache"
import { Map as MaplibreMap } from "maplibre-gl"

type MinimapEntry = {
  container: HTMLDivElement
  map: MaplibreMap
  attached: boolean
}

const getStash = memoize(() => {
  const stash = document.createElement("div")
  stash.hidden = true
  document.body.append(stash)
  return stash
})

const entries = new Map<LayerId, MinimapEntry>()

const ensure = (layerId: LayerId) => {
  const existing = entries.get(layerId)
  if (existing) return existing

  const config = layersConfig.get(layerId)
  assertExists(config, `Minimap layer not found: ${layerId}`)

  const container = document.createElement("div")
  getStash().append(container)

  console.debug("MinimapPool: Initializing minimap", layerId)
  const minimap = new MaplibreMap({
    container,
    attributionControl: false,
    interactive: false,
    refreshExpiredTiles: false,
  })
  configureDefaultMapBehavior(minimap)
  addMapLayerSources(minimap, layerId)
  addMapLayer(minimap, layerId, false)

  if (!config.isBaseLayer) minimap.setPaintProperty(layerId, "raster-opacity", 1)

  const entry: MinimapEntry = { container, map: minimap, attached: false }
  entries.set(layerId, entry)
  return entry
}

const attach = (layerId: LayerId, host: HTMLElement, from: MaplibreMap) => {
  const entry = ensure(layerId)
  host.replaceChildren(entry.container)
  entry.attached = true
  entry.map.resize()
  entry.map.jumpTo({ center: from.getCenter(), zoom: from.getZoom() })
}

const detach = (layerId: LayerId) => {
  const entry = entries.get(layerId)!
  const stash = getStash()
  stash.append(entry.container)
  entry.attached = false
}

const syncFrom = (map: MaplibreMap, kind: "jump" | "ease") => {
  const options = { center: map.getCenter(), zoom: map.getZoom() }
  for (const entry of entries.values()) {
    if (!entry.attached) continue
    if (kind === "jump") {
      entry.map.resize()
      entry.map.jumpTo(options)
    } else {
      entry.map.easeTo(options)
    }
  }
}

export const MinimapPool = { attach, detach, syncFrom }
