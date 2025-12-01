import { fromBinary } from "@bufbuild/protobuf"
import type {
    GeoJSONSource,
    LngLatBounds,
    MapLayerMouseEvent,
    Map as MaplibreMap,
} from "maplibre-gl"
import { routerNavigateStrict } from "../../../index/_router"
import { toggleLayerSpinner } from "../../../index/sidebar/layers"
import { config } from "../../config"
import { RenderElementsDataSchema } from "../../proto/shared_pb"
import { qsEncode } from "../../qs"
import type { OSMNode, OSMWay } from "../../types"
import { getMapAlert } from "../alert"
import { clearMapHover, setMapHover } from "../hover"
import { convertRenderElementsData, renderObjects } from "../render-objects"
import { getLngLatBoundsSize, padLngLatBounds } from "../utils"
import {
    addLayerEventHandler,
    emptyFeatureCollection,
    getExtendedLayerId,
    type LayerCode,
    type LayerId,
    layersConfig,
} from "./layers"

const layerId = "data" as LayerId
const themeColor = "#38f"
const hoverThemeColor = "#f90"
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerCode: "D" as LayerCode,
    layerTypes: ["line", "circle"],
    layerOptions: {
        layout: {
            "line-cap": "round",
            "line-join": "round",
        },
        paint: {
            "line-color": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                hoverThemeColor,
                themeColor,
            ],
            "line-width": 3,
            "circle-radius": 10,
            "circle-color": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                hoverThemeColor,
                themeColor,
            ],
            "circle-opacity": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                0.4,
                0.2,
            ],
            "circle-stroke-color": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                hoverThemeColor,
                themeColor,
            ],
            "circle-stroke-width": 3,
        },
    },
    priority: 100,
})

const loadDataAlertThreshold = 10_000

/** Configure the data layer for the given map */
export const configureDataLayer = (map: MaplibreMap): void => {
    const source = map.getSource(layerId) as GeoJSONSource
    const errorDataAlert = getMapAlert("data-layer-error-alert")
    const loadDataAlert = getMapAlert("data-layer-load-alert")
    const hideDataButton = loadDataAlert.querySelector("button.hide-data-btn")
    const showDataButton = loadDataAlert.querySelector("button.show-data-btn")
    const dataOverlayCheckbox = document.querySelector(
        ".leaflet-sidebar.layers input.overlay[value=data]",
    )

    let enabled = false
    let abortController: AbortController | null = null
    let fetchedBounds: LngLatBounds | null = null
    let fetchedElements: (OSMNode | OSMWay)[] | null = null
    let loadDataOverride = false

    const clearData = (): void => {
        fetchedBounds = null
        fetchedElements = null
        source.setData(emptyFeatureCollection)
        clearMapHover(map, layerId)
    }

    /** On feature click, navigate to the object page */
    const onFeatureClick = (e: MapLayerMouseEvent): void => {
        const props = e.features[0].properties
        routerNavigateStrict(`/${props.type}/${props.id}`)
    }

    let hoveredFeatureId: number | null = null
    const onFeatureHover = (e: MapLayerMouseEvent): void => {
        const feature = e.features[0]
        const featureId = feature.id as number
        if (hoveredFeatureId) {
            if (hoveredFeatureId === featureId) return
            map.removeFeatureState({ source: layerId, id: hoveredFeatureId })
        } else {
            setMapHover(map, layerId)
        }
        hoveredFeatureId = featureId
        map.setFeatureState({ source: layerId, id: hoveredFeatureId }, { hover: true })
    }
    const onFeatureLeave = (): void => {
        map.removeFeatureState({ source: layerId, id: hoveredFeatureId })
        hoveredFeatureId = null
        clearMapHover(map, layerId)
    }

    for (const type of ["fill", "line", "circle"] as const) {
        const extendedLayerId = getExtendedLayerId(layerId, type)
        map.on("click", extendedLayerId, onFeatureClick)
        map.on("mousemove", extendedLayerId, onFeatureHover)
        map.on("mouseleave", extendedLayerId, onFeatureLeave)
    }

    /** Load map data into the data layer */
    const loadData = (): void => {
        console.debug("Loading", fetchedElements.length, "elements")
        loadDataAlert.classList.add("d-none")
        source.setData(renderObjects(fetchedElements, { renderAreas: false }))
    }

    /** Display data alert if not already shown */
    const showDataAlert = (): void => {
        console.debug("Requested too much data, showing alert")
        if (!loadDataAlert.classList.contains("d-none")) return
        showDataButton.addEventListener("click", onShowDataButtonClick, { once: true })
        hideDataButton.addEventListener("click", onHideDataButtonClick, { once: true })
        loadDataAlert.classList.remove("d-none")
    }

    /** On show data click, mark override and load data */
    const onShowDataButtonClick = () => {
        if (loadDataOverride) return
        console.debug("onShowDataButtonClick")
        loadDataOverride = true
        loadDataAlert.classList.add("d-none")
        fetchedElements = []
        fetchedBounds = null
        updateLayer()
    }

    /** On hide data click, uncheck the data layer checkbox */
    const onHideDataButtonClick = () => {
        if (dataOverlayCheckbox.checked === false) return
        console.debug("onHideDataButtonClick")
        dataOverlayCheckbox.checked = false
        dataOverlayCheckbox.dispatchEvent(new Event("change"))
        loadDataAlert.classList.add("d-none")
    }

    /** On map update, fetch the elements in view and update the data layer */
    const updateLayer = (): void => {
        // Skip if the notes layer is not visible
        if (!enabled) return

        // Abort any pending request
        abortController?.abort()
        abortController = new AbortController()

        const viewBounds = map.getBounds()

        // Skip updates if the view is satisfied
        if (
            fetchedBounds?.contains(viewBounds.getSouthWest()) &&
            fetchedBounds.contains(viewBounds.getNorthEast()) &&
            loadDataAlert.classList.contains("d-none")
        )
            return

        // Pad the bounds to reduce refreshes
        const fetchBounds = padLngLatBounds(viewBounds, 0.3)

        // Skip updates if the area is too big
        const area = getLngLatBoundsSize(fetchBounds)
        if (area > config.mapQueryAreaMaxSize) {
            errorDataAlert.classList.remove("d-none")
            loadDataAlert.classList.add("d-none")
            clearData()
            return
        }

        errorDataAlert.classList.add("d-none")
        const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds
            .adjustAntiMeridian()
            .toArray()

        toggleLayerSpinner(layerId, true)
        fetch(
            `/api/web/map?${qsEncode({
                bbox: `${minLon},${minLat},${maxLon},${maxLat}`,
                limit: loadDataOverride ? "" : loadDataAlertThreshold.toString(),
            })}`,
            { signal: abortController.signal, priority: "high" },
        )
            .then(async (resp) => {
                toggleLayerSpinner(layerId, false)
                if (!resp.ok) {
                    if (resp.status === 400) {
                        errorDataAlert.classList.remove("d-none")
                        loadDataAlert.classList.add("d-none")
                        clearData()
                        return
                    }
                    throw new Error(`${resp.status} ${resp.statusText}`)
                }

                const buffer = await resp.arrayBuffer()
                const render = fromBinary(
                    RenderElementsDataSchema,
                    new Uint8Array(buffer),
                )
                fetchedElements = convertRenderElementsData(render)
                fetchedBounds = fetchBounds
                if (render.tooMuchData) {
                    showDataAlert()
                } else {
                    loadData()
                }
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                toggleLayerSpinner(layerId, false)
                clearData()
            })
    }
    map.on("moveend", updateLayer)

    addLayerEventHandler((isAdded, eventLayerId) => {
        if (eventLayerId !== layerId) return
        enabled = isAdded
        if (isAdded) {
            updateLayer()
        } else {
            errorDataAlert.classList.add("d-none")
            loadDataAlert.classList.add("d-none")
            abortController?.abort()
            abortController = null
            toggleLayerSpinner(layerId, false)
            clearData()
        }
    })
}
