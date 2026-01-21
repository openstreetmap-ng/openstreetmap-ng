import { ChangesetRoute } from "@index/changeset"
import { ChangesetsHistoryRoute } from "@index/changesets-history"
import { configureContextMenu } from "@index/context-menu"
import { DistanceRoute } from "@index/distance"
import { ElementRoute } from "@index/element"
import { ElementHistoryRoute } from "@index/element-history"
import { ExportRoute } from "@index/export"
import { IndexRoute } from "@index/index"
import { NewNoteRoute } from "@index/new-note"
import { NoteRoute } from "@index/note"
import { QueryFeaturesRoute } from "@index/query-features"
import { configureRouter } from "@index/router"
import { IndexRouterOutlet } from "@index/router-outlet"
import { RoutingRoute } from "@index/routing"
import { SearchRoute } from "@index/search"
import { configureSearchForm } from "@index/search-form"
import { LayerSidebarToggleControl } from "@index/sidebar/layers"
import { LegendSidebarToggleControl } from "@index/sidebar/legend"
import { ShareSidebarToggleControl } from "@index/sidebar/share"
import { globeProjectionStorage, mapStateStorage } from "@lib/local-storage"
import { wrapIdleCallbackStatic } from "@lib/polyfills"
import { effect } from "@preact/signals"
import { Map as MaplibreMap, ScaleControl } from "maplibre-gl"
import { render } from "preact"
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

  configureRouter([
    IndexRoute,

    ChangesetRoute,
    ChangesetsHistoryRoute,
    DistanceRoute,
    ElementHistoryRoute,
    ElementRoute,
    ExportRoute,
    NewNoteRoute,
    NoteRoute,
    QueryFeaturesRoute,
    RoutingRoute,
    SearchRoute,
  ])

  const actionSidebar = document.getElementById("ActionSidebar")!
  render(<IndexRouterOutlet map={map} />, actionSidebar)

  handleEditRemotePath()
}

const mapContainer = document.getElementById("MainMap")
if (mapContainer?.tagName === "DIV") configureMainMap(mapContainer)
