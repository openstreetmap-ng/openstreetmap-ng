import { Map as MaplibreMap, ScaleControl } from "maplibre-gl"
import { homePoint } from "../_config"
import { handleEditRemotePath, updateNavbarAndHash } from "../_navbar"
import { isMetricUnit } from "../_unit.ts"
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
import { configureRouter } from "../index/_router"
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

/** Get the main map instance */
const createMainMap = (container: HTMLElement): MaplibreMap => {
    console.debug("Initializing main map")
    const map = new MaplibreMap({
        container,
        maxZoom: 19,
        attributionControl: { compact: true, customAttribution: "" },
        refreshExpiredTiles: false,
        canvasContextAttributes: { alpha: false, preserveDrawingBuffer: true },
        fadeDuration: 0,
    })
    configureDefaultMapBehavior(map)
    addMapLayerSources(map, "all")

    map.addControl(
        new ScaleControl({
            unit: isMetricUnit ? "metric" : "imperial",
        }),
    )

    // Add custom controls
    addControlGroup(map, [new CustomZoomControl(), new CustomGeolocateControl()])
    addControlGroup(map, [
        new LayersSidebarToggleControl(),
        new LegendSidebarToggleControl(),
        new ShareSidebarToggleControl(),
    ])
    addControlGroup(map, [new NewNoteControl()])
    addControlGroup(map, [new QueryFeaturesControl()])

    // Configure map handlers
    configureNotesLayer(map)
    configureDataLayer(map)
    configureContextMenu(map)

    // On map state change, update the navbar and hash
    map.on("moveend", () => updateNavbarAndHash(getMapState(map)))
    addLayerEventHandler(() => updateNavbarAndHash(getMapState(map)))

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

    setMapState(map, getInitialMapState(map), { animate: false })
    return map
}

/** Configure the main map and all its components */
const configureMainMap = (container: HTMLElement): void => {
    const map = createMainMap(container)

    // Configure here instead of navbar to avoid global script dependency (navbar is global)
    // Find home button is only available for the users with configured home location
    if (homePoint) {
        const findHomeContainer = document.querySelector(".find-home-container")
        const findHomeButton = findHomeContainer.querySelector("button")
        configureFindHomeButton(map, findHomeButton, homePoint)
        findHomeContainer.classList.remove("d-none")
    }

    configureRouter(
        new Map([
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
