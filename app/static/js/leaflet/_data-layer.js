import * as L from "leaflet"
import { mapQueryAreaMaxSize } from "../_config.js"
import "../_types.js"
import { routerNavigateStrict } from "../index/_router.js"
import { getOverlayLayerById } from "./_layers.js"
import { getMapAlert } from "./_map-utils.js"
import { renderObjects } from "./_object-render.js"
import { getLatLngBoundsSize } from "./_utils.js"

const loadDataAlertThreshold = 8000

export const dataStyles = {
    element: {
        color: "#3388FF",
        weight: 3,
        opacity: 1,
        fillOpacity: 0.4,
        interactive: true,
    },
}

/**
 * Configure the data layer for the given map
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const configureDataLayer = (map) => {
    const dataLayer = getOverlayLayerById("data")
    const errorDataAlert = getMapAlert("data-layer-error-alert")
    const loadDataAlert = getMapAlert("data-layer-load-alert")
    const hideDataButton = loadDataAlert.querySelector(".hide-data")
    const showDataButton = loadDataAlert.querySelector(".show-data")
    const dataOverlayCheckbox = document.querySelector(".leaflet-sidebar.layers input.overlay[value=data]")
    let abortController = null
    let fetchedBounds = null
    let fetchedElements = null
    let loadDataOverride = null

    const clearData = () => {
        fetchedBounds = null
        fetchedElements = null
        dataLayer.clearLayers()
    }

    /**
     * On layer click, navigate to the object page
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerClick = (event) => {
        const layer = event.target
        const object = layer.object
        routerNavigateStrict(`/${object.type}/${object.id}`)
    }

    /**
     * On map update, fetch the elements in view and update the data layer
     * @returns {void}
     */
    const onMapZoomOrMoveEnd = () => {
        // Skip if the notes layer is not visible
        if (!map.hasLayer(dataLayer)) return

        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        const viewBounds = map.getBounds()

        // Skip updates if the view is satisfied
        if (fetchedBounds?.contains(viewBounds)) return

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

    /**
     * Attempt to load map data, show alert if too much data
     * @returns {void}
     */
    const tryLoadData = () => {
        if (fetchedElements.length < loadDataAlertThreshold || loadDataOverride) {
            console.log(fetchedElements.length)
            loadData()
            return
        }
        if (!loadDataAlert.classList.contains("d-none")) return
        console.debug("Loaded", fetchedElements.length, "elements, deciding whether to show data")
        showDataButton.addEventListener("click", onShowDataClick, { once: true })
        hideDataButton.addEventListener("click", onHideDataClick, { once: true })
        loadDataAlert.classList.remove("d-none")
    }

    /**
     * Load map data into the data layer
     * @returns {void}
     */
    const loadData = () => {
        const layerGroup = L.layerGroup()
        const renderLayers = renderObjects(layerGroup, fetchedElements, dataStyles, { renderAreas: false })

        dataLayer.clearLayers()
        dataLayer.addLayer(layerGroup)
        // Listen for events
        for (const layer of renderLayers) layer.addEventListener("click", onLayerClick)
    }

    // On show data click, mark override and load data
    const onShowDataClick = () => {
        if (loadDataOverride) return
        console.debug("Decided to show data layer")
        loadDataOverride = true
        loadDataAlert.classList.add("d-none")
        loadData()
    }

    // On hide data click, uncheck the data layer checkbox
    const onHideDataClick = () => {
        if (dataOverlayCheckbox.checked === false) return
        console.debug("Decided to hide data layer")
        dataOverlayCheckbox.checked = false
        dataOverlayCheckbox.dispatchEvent(new Event("change"))
        loadDataAlert.classList.add("d-none")
    }

    /**
     * On overlay add, update the data layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayAdd = ({ name }) => {
        if (name !== "data") return
        // Listen for events and run initial update
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        onMapZoomOrMoveEnd()
    }

    /**
     * On overlay remove, abort any pending request and clear the data layer
     * @param {L.LayersControlEvent} event
     * @returns {void}
     */
    const onOverlayRemove = ({ name }) => {
        if (name !== "data") return

        errorDataAlert.classList.add("d-none")
        loadDataAlert.classList.add("d-none")
        showDataButton.removeEventListener("click", onShowDataClick)
        hideDataButton.removeEventListener("click", onHideDataClick)
        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        if (abortController) abortController.abort()
        abortController = null
        clearData()
    }

    // Listen for events
    map.addEventListener("overlayadd", onOverlayAdd)
    map.addEventListener("overlayremove", onOverlayRemove)
}
