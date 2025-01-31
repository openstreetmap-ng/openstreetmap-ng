import { Map as MaplibreMap, ScaleControl } from "maplibre-gl"
import { config } from "../_config"
import { isMetricUnit } from "../_intl.ts"
import { setLastMapState } from "../_local-storage.ts"
import { handleEditRemotePath, updateNavbarAndHash } from "../_navbar"
import { wrapIdleCallbackStatic } from "../_utils.ts"
import { getChangesetController } from "../index/_changeset"
import { getChangesetsHistoryController } from "../index/_changesets-history"
import { getDistanceController } from "../index/_distance"
import { getElementController } from "../index/_element"
import { getElementHistoryController } from "../index/_element-history"
import { getExportController } from "../index/_export"
import { getIndexController } from "../index/_index"
import { getNewNoteController } from "../index/_new-note"
import { getNoteController } from "../index/_note"
import { getQueryFeaturesController } from "../index/_query-features"
import { type IndexController, configureRouter } from "../index/_router"
import { getRoutingController } from "../index/_routing"
import { getSearchController } from "../index/_search"
import { configureSearchForm } from "../index/_search-form"
import { configureContextMenu } from "./_context-menu"
import { configureDataLayer } from "./_data-layer"
import { configureFindHomeButton } from "./_find-home"
import { CustomGeolocateControl } from "./_geolocate.ts"
import { addLayerEventHandler, addMapLayerSources } from "./_layers.ts"
import { addControlGroup, getInitialMapState, getMapState, parseMapState, setMapState } from "./_map-utils"
import { NewNoteControl } from "./_new-note.ts"
import { configureNotesLayer } from "./_notes-layer"
import { QueryFeaturesControl } from "./_query-features.ts"
import { LayersSidebarToggleControl } from "./_sidebar-layers.ts"
import { LegendSidebarToggleControl } from "./_sidebar-legend.ts"
import { ShareSidebarToggleControl } from "./_sidebar-share.ts"
import { configureDefaultMapBehavior } from "./_utils.ts"
import { CustomZoomControl } from "./_zoom.ts"
import { CustomGlobeControl } from "./_globe.ts"

/** Get the main map instance */
const createMainMap = (container: HTMLElement): MaplibreMap => {
    console.debug("Initializing main map")
    const map = new MaplibreMap({
        container,
        minZoom: 0,
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
    addMapLayerSources(map, "all")
    configureNotesLayer(map)
    configureDataLayer(map)
    configureContextMenu(map)

    const saveMapStateLazy = wrapIdleCallbackStatic(() => {
        const state = getMapState(map)
        updateNavbarAndHash(state)
        setLastMapState(state)
    })
    map.on("moveend", saveMapStateLazy)
    addLayerEventHandler(saveMapStateLazy)

    // Add controls to the map
    map.addControl(
        new ScaleControl({
            unit: isMetricUnit() ? "metric" : "imperial",
        }),
    )
    addControlGroup(map, [new CustomZoomControl(), new CustomGeolocateControl(), new CustomGlobeControl()])
    addControlGroup(map, [
        new LayersSidebarToggleControl(),
        new LegendSidebarToggleControl(),
        new ShareSidebarToggleControl(),
    ])
    addControlGroup(map, [new NewNoteControl()])
    addControlGroup(map, [new QueryFeaturesControl()])

    // On hash change, update the map view
    window.addEventListener("hashchange", () => {
        // TODO: check if no double setMapState triggered
        console.debug("onHashChange", location.hash)
        let newState = parseMapState(location.hash)
        if (!newState) {
            // Get the current state if empty/invalid and replace the hash
            newState = getMapState(map)
            updateNavbarAndHash(newState)
        }
        setMapState(map, newState)
    })

    // Finally set the initial state that will trigger map events
    setMapState(map, getInitialMapState(map), { animate: false })
    return map
}

/** Configure the main map and all its components */
const configureMainMap = (container: HTMLElement): void => {
    const map = createMainMap(container)

    // Configure here instead of navbar to avoid global script dependency (navbar is global)
    // Find home button is only available for the users with configured home location
    const homePoint = config.userConfig?.homePoint
    if (homePoint) {
        const findHomeContainer = document.querySelector(".find-home-container")
        const findHomeButton = findHomeContainer.querySelector("button")
        configureFindHomeButton(map, findHomeButton, homePoint)
        findHomeContainer.classList.remove("d-none")
    }

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
            ["/note/(?<id>\\d+)", getNoteController(map)],
            ["/changeset/(?<id>\\d+)", getChangesetController(map)],
            ["/(?<type>node|way|relation)/(?<id>\\d+)(?:/history/(?<version>\\d+))?", getElementController(map)],
            ["/(?<type>node|way|relation)/(?<id>\\d+)/history", getElementHistoryController(map)],
            ["/distance", getDistanceController(map)],
        ]),
    )

    configureSearchForm(map)
    handleEditRemotePath()
}

const mapContainer = document.querySelector("div.main-map")
if (mapContainer) configureMainMap(mapContainer)
