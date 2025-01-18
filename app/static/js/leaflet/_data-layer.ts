import { fromBinary } from "@bufbuild/protobuf"
import type { GeoJSONSource, LngLatBounds, Map as MaplibreMap, MapGeoJSONFeature, MapMouseEvent } from "maplibre-gl"
import { mapQueryAreaMaxSize } from "../_config"
import { qsEncode } from "../_qs"
import type { OSMNode, OSMWay } from "../_types"
import { routerNavigateStrict } from "../index/_router"
import { RenderElementsDataSchema } from "../proto/shared_pb"
import { getMapAlert } from "./_alert"
import {
    addLayerEventHandler,
    emptyFeatureCollection,
    hasMapLayer,
    type LayerCode,
    type LayerId,
    layersConfig,
    makeExtendedLayerId,
} from "./_layers"
import { convertRenderElementsData, renderObjects } from "./_render-objects"
import { getLngLatBoundsSize, padLngLatBounds } from "./_utils"

const layerId = "data" as LayerId
const themeColor = "#3388ff"
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerCode: "D" as LayerCode,
    layerTypes: ["fill", "line", "circle"],
    layerOptions: {
        layout: {
            "line-cap": "round",
            "line-join": "round",
        },
        paint: {
            "fill-opacity": 0.4,
            "fill-color": themeColor,
            "line-color": themeColor,
            "line-width": 3,
            "circle-radius": 10,
            "circle-color": themeColor,
            "circle-opacity": 0.4,
            "circle-stroke-width": 3,
            "circle-stroke-color": themeColor,
        },
    },
    priority: 100,
})

const loadDataAlertThreshold = 8000

/** Configure the data layer for the given map */
export const configureDataLayer = (map: MaplibreMap): void => {
    const source = map.getSource(layerId) as GeoJSONSource
    const errorDataAlert = getMapAlert("data-layer-error-alert")
    const loadDataAlert = getMapAlert("data-layer-load-alert")
    const hideDataButton = loadDataAlert.querySelector("button.hide-data-btn")
    const showDataButton = loadDataAlert.querySelector("button.show-data-btn")
    const dataOverlayCheckbox = document.querySelector(".leaflet-sidebar.layers input.overlay[value=data]")

    let enabled = hasMapLayer(map, layerId)
    let abortController: AbortController | null = null
    let fetchedBounds: LngLatBounds | null = null
    let fetchedElements: (OSMNode | OSMWay)[] | null = null
    let loadDataOverride = false

    const clearData = (): void => {
        fetchedBounds = null
        fetchedElements = null
        source.setData(emptyFeatureCollection)
    }

    /** On feature click, navigate to the object page */
    const onFeatureClick = (e: MapMouseEvent & { features?: MapGeoJSONFeature[] }): void => {
        const props = e.features[0].properties
        routerNavigateStrict(`/${props.type}/${props.id}`)
    }
    for (const type of ["fill", "line", "circle"]) {
        map.on("click", makeExtendedLayerId(layerId, type), onFeatureClick)
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
        if (area > mapQueryAreaMaxSize) {
            errorDataAlert.classList.remove("d-none")
            loadDataAlert.classList.add("d-none")
            clearData()
            return
        }

        errorDataAlert.classList.add("d-none")
        const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds.adjustAntiMeridian().toArray()

        fetch(
            `/api/web/map?${qsEncode({
                bbox: `${minLon},${minLat},${maxLon},${maxLat}`,
                limit: loadDataOverride ? "" : loadDataAlertThreshold.toString(),
            })}`,
            {
                method: "GET",
                mode: "same-origin",
                cache: "no-store", // request params are too volatile to cache
                signal: abortController.signal,
                priority: "high",
            },
        )
            .then(async (resp) => {
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
                const render = fromBinary(RenderElementsDataSchema, new Uint8Array(buffer))
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
            clearData()
        }
    })
}
