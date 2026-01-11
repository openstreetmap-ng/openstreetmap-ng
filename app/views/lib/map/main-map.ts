import { getChangesetController } from "@index/changeset"
import { getChangesetsHistoryController } from "@index/changesets-history"
import { configureContextMenu } from "@index/context-menu"
import { getDistanceController } from "@index/distance"
import { getElementController } from "@index/element"
import { getElementHistoryController } from "@index/element-history"
import { getExportController } from "@index/export"
import { getIndexController } from "@index/index"
import { getNewNoteController } from "@index/new-note"
import { getNoteController } from "@index/note"
import { getQueryFeaturesController } from "@index/query-features"
import { configureRouter, type IndexController } from "@index/router"
import { getRoutingController } from "@index/routing"
import { getSearchController } from "@index/search"
import { configureSearchForm } from "@index/search-form"
import { LayerSidebarToggleControl } from "@index/sidebar/layers"
import { LegendSidebarToggleControl } from "@index/sidebar/legend"
import { ShareSidebarToggleControl } from "@index/sidebar/share"
import { globeProjectionStorage, mapStateStorage } from "@lib/local-storage"
import { wrapIdleCallbackStatic } from "@lib/polyfills"
import { effect } from "@preact/signals"
import { Map as MaplibreMap, ScaleControl } from "maplibre-gl"
import { handleEditRemotePath, updateNavbarAndHash } from "../../navbar/navbar"
import { CustomGeolocateControl } from "./controls/geolocate"
import { addControlGroup } from "./controls/group"
import { NewNoteControl } from "./controls/new-note"
import { QueryFeaturesControl } from "./controls/query-features"
import { CustomZoomControl } from "./controls/zoom"
import { configureDefaultMapBehavior } from "./defaults"
import { configureDataLayer } from "./layers/data-layer"
import { addLayerEventHandler, addMapLayerSources } from "./layers/layers"
import { configureNotesLayer } from "./layers/notes-layer"
import { applyMapState, getInitialMapState, getMapState, parseMapState } from "./state"

/** Get the main map instance */
const createMainMap = (container: HTMLElement) => {
  console.debug("MainMap: Initializing")
  const map = new MaplibreMap({
    container,
    minZoom: 1,
    maxZoom: 19,
    attributionControl: { compact: true, customAttribution: "" },
    refreshExpiredTiles: false,
    canvasContextAttributes: { alpha: false, preserveDrawingBuffer: true },
    fadeDuration: 0,
  })
  map.once("style.load", () => {
    // Disable transitions after loading the style
    map.style.stylesheet.transition = { duration: 0 }
  })
  configureDefaultMapBehavior(map)

  let globeWasEnabled: boolean | null = null
  effect(() => {
    const enabled = globeProjectionStorage.value
    if (globeWasEnabled === enabled) return

    const prevEnabled = globeWasEnabled
    globeWasEnabled = enabled

    map.setProjection({ type: enabled ? "globe" : "mercator" })

    // Workaround a bug where after switching back to mercator,
    // the map is not fit to the screen (there is grey padding).
    if (prevEnabled === true && enabled === false) map.resize()
  })

  addMapLayerSources(map, "all")
  configureNotesLayer(map)
  configureDataLayer(map)
  configureContextMenu(map)

  const saveMapStateLazy = wrapIdleCallbackStatic(() => {
    const state = getMapState(map)
    updateNavbarAndHash(state)
    mapStateStorage.set(state)
  })
  map.on("moveend", saveMapStateLazy)
  addLayerEventHandler(saveMapStateLazy)

  // On hash change, update the map view
  window.addEventListener("hashchange", () => {
    console.debug("MainMap: Hash changed", location.hash)
    const newState = parseMapState(location.hash)
    if (newState) applyMapState(map, newState)
    saveMapStateLazy()
  })

  // Finally set the initial state that will trigger map events
  applyMapState(map, getInitialMapState(map), { animate: false })
  saveMapStateLazy()

  map.addControl(new ScaleControl({ unit: "imperial" }))
  map.addControl(new ScaleControl({ unit: "metric" }))
  addControlGroup(map, [new CustomZoomControl(), new CustomGeolocateControl()])
  addControlGroup(map, [
    new LayerSidebarToggleControl(),
    new LegendSidebarToggleControl(),
    new ShareSidebarToggleControl(),
  ])
  addControlGroup(map, [new NewNoteControl()])
  addControlGroup(map, [new QueryFeaturesControl()])

  return map
}

/** Configure the main map and all its components */
const configureMainMap = (container: HTMLElement) => {
  const map = createMainMap(container)

  configureSearchForm(map)

  configureRouter(
    new Map<string, IndexController>([
      ["/", getIndexController(map)],
      ["/export", getExportController(map)],
      ["/directions", getRoutingController(map)],
      ["/search", getSearchController(map)],
      ["/query", getQueryFeaturesController(map)],
      [
        "(?:/history(?:/(?<scope>nearby|friends))?|/user/(?<displayName>[^/]+)/history)",
        getChangesetsHistoryController(map),
      ],
      ["/note/new", getNewNoteController(map)],
      ["/note/(?<id>\\d+)(?:/unsubscribe)?", getNoteController(map)],
      ["/changeset/(?<id>\\d+)(?:/unsubscribe)?", getChangesetController(map)],
      [
        "/(?<type>node|way|relation)/(?<id>\\d+)(?:/history/(?<version>\\d+))?",
        getElementController(map),
      ],
      [
        "/(?<type>node|way|relation)/(?<id>\\d+)/history",
        getElementHistoryController(map),
      ],
      ["/distance", getDistanceController(map)],
    ]),
  )

  handleEditRemotePath()
}

const mapContainer = document.querySelector("div.main-map")
if (mapContainer) configureMainMap(mapContainer)
