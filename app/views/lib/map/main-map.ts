import { Map as MaplibreMap, ScaleControl } from "maplibre-gl"
import { config } from "../config"
import { isMetricUnit } from "../intl"
import { mapStateStorage } from "../local-storage"
import { handleEditRemotePath, updateNavbarAndHash } from "../../navbar/navbar"
import { wrapIdleCallbackStatic } from "../utils"
import { getChangesetController } from "../../index/changeset"
import { getChangesetsHistoryController } from "../../index/changesets-history"
import { getDistanceController } from "../../index/distance"
import { getElementController } from "../../index/element"
import { getElementHistoryController } from "../../index/element-history"
import { getExportController } from "../../index/export"
import { getIndexController } from "../../index/index"
import { getNewNoteController } from "../../index/new-note"
import { getNoteController } from "../../index/note"
import { getQueryFeaturesController } from "../../index/query-features"
import { type IndexController, configureRouter } from "../../index/_router"
import { getRoutingController } from "../../index/routing"
import { getSearchController } from "../../index/search"
import { configureSearchForm } from "../../index/search-form"
import { configureContextMenu } from "../../index/context-menu"
import { configureDataLayer } from "./data-layer"
import { configureFindHomeButton } from "./find-home"
import { CustomGeolocateControl } from "./geolocate"
import { addLayerEventHandler, addMapLayerSources } from "./layers"
import {
    addControlGroup,
    getInitialMapState,
    getMapState,
    parseMapState,
    setMapState,
} from "./map-utils"
import { NewNoteControl } from "./new-note"
import { configureNotesLayer } from "./notes-layer"
import { QueryFeaturesControl } from "./query-features"
import { LayersSidebarToggleControl } from "../../index/sidebar/layers"
import { LegendSidebarToggleControl } from "../../index/sidebar/legend"
import { ShareSidebarToggleControl } from "../../index/sidebar/share"
import { configureDefaultMapBehavior } from "./utils"
import { CustomZoomControl } from "./zoom"

/** Get the main map instance */
const createMainMap = (container: HTMLElement): MaplibreMap => {
    console.debug("Initializing main map")
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

    // Add controls to the map
    map.addControl(
        new ScaleControl({
            unit: isMetricUnit() ? "metric" : "imperial",
        }),
    )
    addControlGroup(map, [new CustomZoomControl(), new CustomGeolocateControl()])
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

    configureSearchForm(map)
    handleEditRemotePath()
}

const mapContainer = document.querySelector("div.main-map")
if (mapContainer) configureMainMap(mapContainer)
