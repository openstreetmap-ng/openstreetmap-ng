import * as L from "leaflet"
import { mapQueryAreaMaxSize } from "../_config"

import type { OSMObject } from "../_types"
import { routerNavigateStrict } from "../index/_router"
import { type LayerId, getOverlayLayerById } from "./_layers"
import { getMapAlert } from "./_map-utils"
import { type RenderStyles, renderObjects } from "./_render-objects"
import { getLatLngBoundsSize } from "./_utils"

const loadDataAlertThreshold = 8000
const dataLayerId = "data" as LayerId

export const dataStyles: RenderStyles = {
    element: {
        color: "#3388FF",
        weight: 3,
        opacity: 1,
        fillOpacity: 0.4,
        interactive: true,
    },
}

/** Configure the data layer for the given map */
export const configureDataLayer = (map: L.Map): void => {
    const dataLayer = getOverlayLayerById(dataLayerId) as L.FeatureGroup
    const errorDataAlert = getMapAlert("data-layer-error-alert")
    const loadDataAlert = getMapAlert("data-layer-load-alert")
    const hideDataButton = loadDataAlert.querySelector("button.hide-data-btn")
    const showDataButton = loadDataAlert.querySelector("button.show-data-btn")
    const dataOverlayCheckbox = document.querySelector(".leaflet-sidebar.layers input.overlay[value=data]")

    let abortController: AbortController | null = null
    let fetchedBounds: L.LatLngBounds | null = null
    let fetchedElements: OSMObject[] | null = null
    let loadDataOverride = false

    const clearData = (): void => {
        fetchedBounds = null
        fetchedElements = null
        dataLayer.clearLayers()
    }

    /** On layer click, navigate to the object page */
    const onLayerClick = (event: L.LeafletMouseEvent): void => {
        const object = event.target.object
        routerNavigateStrict(`/${object.type}/${object.id}`)
    }

    /** Load map data into the data layer */
    const loadData = (): void => {
        console.debug("Loading", fetchedElements.length, "elements")
        const layerGroup = L.layerGroup()
        const renderLayers = renderObjects(layerGroup, fetchedElements, dataStyles, { renderAreas: false })

        dataLayer.clearLayers()
        dataLayer.addLayer(layerGroup)
        for (const layer of renderLayers) layer.addEventListener("click", onLayerClick)
    }

    /** Attempt to load map data, show alert if too much data */
    const tryLoadData = (): void => {
        if (fetchedElements.length < loadDataAlertThreshold || loadDataOverride) {
            loadDataAlert.classList.add("d-none")
            loadData()
            return
        }
        if (!loadDataAlert.classList.contains("d-none")) return
        console.debug("Fetched", fetchedElements.length, "elements, deciding whether to show data")
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
        loadData()
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
    const onMapZoomOrMoveEnd = (): void => {
        // Skip if the notes layer is not visible
        if (!map.hasLayer(dataLayer)) return

        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        const viewBounds = map.getBounds()

        // Skip updates if the view is satisfied
        if (fetchedBounds?.contains(viewBounds) && loadDataAlert.classList.contains("d-none")) return

        // Pad the bounds to reduce refreshes
        const bounds = viewBounds.pad(0.3)

        // Skip updates if the area is too big
        const area = getLatLngBoundsSize(bounds)
        if (area > mapQueryAreaMaxSize) {
            errorDataAlert.classList.remove("d-none")
            loadDataAlert.classList.add("d-none")
            clearData()
            return
        }

        errorDataAlert.classList.add("d-none")
        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()

        fetch(`/api/web/map?bbox=${minLon},${minLat},${maxLon},${maxLat}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: abortController.signal,
            priority: "high",
        })
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
                fetchedElements = await resp.json()
                fetchedBounds = bounds
                tryLoadData()
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                clearData()
            })
    }

    // On overlay add, configure the data layer
    map.addEventListener("overlayadd", ({ name }: L.LayersControlEvent): void => {
        if (name !== dataLayerId) return
        // Listen for events and run initial update
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        onMapZoomOrMoveEnd()
    })

    // On overlay remove, abort any pending request and clear the data layer
    map.addEventListener("overlayremove", ({ name }: L.LayersControlEvent): void => {
        if (name !== dataLayerId) return
        errorDataAlert.classList.add("d-none")
        loadDataAlert.classList.add("d-none")
        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        if (abortController) abortController.abort()
        abortController = null
        clearData()
    })
}
