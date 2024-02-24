import { Tooltip } from "bootstrap"
import * as L from "leaflet"
import { mapQueryAreaMaxSize, noteQueryAreaMaxSize } from "../_config.js"
import { getBaseLayerById, getOverlayLayerById } from "./_layers.js"
import { cloneTileLayer, getMapBaseLayerId } from "./_map-utils.js"
import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"
import { getLatLngBoundsSize } from "./_utils.js"

const minimapZoomOut = 2

export const getLayersSidebarToggleButton = () => {
    const control = getSidebarToggleButton("layers", "javascripts.map.layers.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const button = control.button

        const minimaps = []
        const layerContainers = sidebar.querySelectorAll(".layer")
        const overlayCheckboxes = sidebar.querySelectorAll("input.overlay")

        // Ensure minimaps have been initialized
        const ensureMinimapsInitialized = () => {
            if (minimaps.length) return

            for (const layerContainer of layerContainers) {
                const layerId = layerContainer.dataset.layerId
                const layer = getBaseLayerById(layerId)
                if (!layer) {
                    console.error("Base layer", layerId, "not found")
                    continue
                }

                console.debug("Initializing minimap for layer", layerId)
                const minimapContainer = layerContainer.querySelector(".leaflet-container")
                const minimap = L.map(minimapContainer, {
                    attributionControl: false,
                    zoomControl: false,
                    boxZoom: false,
                    doubleClickZoom: false,
                    dragging: false,
                    keyboard: false,
                    scrollWheelZoom: false,
                    touchZoom: false,
                })

                minimap.addLayer(cloneTileLayer(layer))
                minimaps.push(minimap)
            }
        }

        // On layer change, update the active container
        const onBaseLayerChange = () => {
            const activeLayerId = getMapBaseLayerId(map)

            for (const layerContainer of layerContainers) {
                const layerId = layerContainer.dataset.layerId
                layerContainer.classList.toggle("active", layerId === activeLayerId)
            }
        }

        // On map zoomend or moveend, update the minimaps view
        const onMapZoomOrMoveEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const center = map.getCenter()
            const zoom = Math.max(map.getZoom() - minimapZoomOut, 0)

            for (const minimap of minimaps) {
                minimap.setView(center, zoom)
            }
        }

        // On map zoomend, update the available overlays
        const onMapZoomEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const currentViewAreaSize = getLatLngBoundsSize(map.getBounds())

            for (const overlayCheckbox of overlayCheckboxes) {
                let areaMaxSize
                const layerId = overlayCheckbox.value
                switch (layerId) {
                    case "notes":
                        areaMaxSize = noteQueryAreaMaxSize
                        break
                    case "data":
                        areaMaxSize = mapQueryAreaMaxSize
                        break
                    default:
                        // Some overlays are always available
                        continue
                }

                const isAvailable = currentViewAreaSize <= areaMaxSize
                if (isAvailable) {
                    if (overlayCheckbox.disabled) {
                        overlayCheckbox.disabled = false

                        const parent = overlayCheckbox.closest(".form-check")
                        parent.classList.remove("disabled")
                        parent.setAttribute("aria-disabled", "false")
                        const tooltip = Tooltip.getInstance(parent)
                        tooltip.disable()
                        tooltip.hide()

                        // Restore the overlay state if it was checked before
                        if (overlayCheckbox.dataset.wasChecked) {
                            console.debug("Restoring checked state for overlay", layerId)
                            overlayCheckbox.dataset.wasChecked = ""
                            overlayCheckbox.checked = true
                            overlayCheckbox.dispatchEvent(new Event("change"))
                        }
                    }
                } else if (!overlayCheckbox.disabled) {
                    overlayCheckbox.blur()
                    overlayCheckbox.disabled = true

                    const parent = overlayCheckbox.closest(".form-check")
                    parent.classList.add("disabled")
                    parent.setAttribute("aria-disabled", "true")
                    Tooltip.getOrCreateInstance(parent, {
                        title: parent.dataset.bsTitle,
                        placement: "top",
                    }).enable()

                    // Force uncheck the overlay when it becomes unavailable
                    if (overlayCheckbox.checked) {
                        console.debug("Forcing unchecked state for overlay", layerId)
                        overlayCheckbox.dataset.wasChecked = true
                        overlayCheckbox.checked = false
                        overlayCheckbox.dispatchEvent(new Event("change"))
                    }
                }
            }
        }

        // On layer click, update the active (base) layer
        const onBaseLayerClick = (e) => {
            const layerContainer = e.currentTarget
            const layerId = layerContainer.dataset.layerId
            const layer = getBaseLayerById(layerId)
            if (!layer) {
                console.error("Base layer", layerId, "not found")
                return
            }

            const activeLayerId = getMapBaseLayerId(map)

            // Skip updates if the layer is already active
            if (layerId === activeLayerId) return

            // Remove all base layers
            map.eachLayer((layer) => {
                const layerId = layer.options.layerId
                if (!layerId) return

                if (getBaseLayerById(layerId)) {
                    console.debug("Removing base layer", layerId)
                    map.removeLayer(layer)
                }
            })

            // Add the new base layer
            console.debug("Adding base layer", layerId)
            map.addLayer(layer)

            // Trigger the baselayerchange event
            // https://leafletjs.com/reference.html#map-baselayerchange
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("baselayerchange", { layer, name: layerId })
        }

        // On overlay checkbox change, add or remove the overlay layer
        const onOverlayCheckboxChange = (e) => {
            console.warn(e)
            const overlayCheckbox = e.currentTarget
            const layerId = overlayCheckbox.value
            const layer = getOverlayLayerById(layerId)
            if (!layer) {
                console.error("Overlay layer", layerId, "not found")
                return
            }

            const checked = overlayCheckbox.checked
            const containsLayer = map.hasLayer(layer)

            // Skip updates if the layer is already in the correct state
            if (checked === containsLayer) return

            // Add or remove the overlay layer
            if (checked) {
                console.debug("Adding overlay layer", layerId)
                map.addLayer(layer)

                // Trigger the overlayadd event
                // https://leafletjs.com/reference.html#map-overlayadd
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayadd", { layer: layer, name: layerId })
            } else {
                console.debug("Removing overlay layer", layerId)
                map.removeLayer(layer)

                // Trigger the overlayremove event
                // https://leafletjs.com/reference.html#map-overlayremove
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayremove", { layer: layer, name: layerId })
            }
        }

        // On sidebar shown, update the minimaps view instantly
        const onButtonClick = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            ensureMinimapsInitialized()
            const center = map.getCenter()
            const zoom = Math.max(map.getZoom() - minimapZoomOut, 0)

            for (const minimap of minimaps) {
                minimap.setView(center, zoom, { animate: false })
            }
        }

        // Listen for events
        map.addEventListener("baselayerchange", onBaseLayerChange)
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        map.addEventListener("zoomend", onMapZoomEnd)
        for (const layerContainer of layerContainers) layerContainer.addEventListener("click", onBaseLayerClick)
        for (const overlayCheckbox of overlayCheckboxes)
            overlayCheckbox.addEventListener("change", onOverlayCheckboxChange)
        button.addEventListener("click", onButtonClick)

        return container
    }

    return control
}
