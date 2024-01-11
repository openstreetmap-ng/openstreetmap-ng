import { Tooltip } from "bootstrap"
import * as L from "leaflet"
import { getBaseLayerById, getOverlayLayerById } from "./_osm.js"
import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"

const minimapZoomOut = 2

export const getLayersSidebarToggleButton = (options) => {
    const control = getSidebarToggleButton(options, "layers", "javascripts.map.layers.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const input = control.input

        const minimaps = []
        const layerContainers = sidebar.querySelectorAll(".layer")
        const overlayCheckboxes = sidebar.querySelectorAll("input.overlay")

        // TODO: invalidateSize ?

        // Initialize the minimap
        for (const layerContainer of layerContainers) {
            const layerId = layerContainer.dataset.layerId
            const layer = getBaseLayerById(layerId)
            if (!layer) {
                console.error(`Base layer ${layerId} not found`)
                continue
            }

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

            minimap.addLayer(layer)
            minimaps.push(minimap)
        }

        // On layer change, update the active container
        const onBaseLayerChange = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            const activeLayerId = map.getBaseLayerId()

            for (const layerContainer of layerContainers) {
                const layerId = layerContainer.dataset.layerId
                layerContainer.classList.toggle("active", layerId === activeLayerId)
            }
        }

        // On map zoomend or moveend, update the minimaps view
        const onMapZoomOrMoveEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            const center = map.getCenter()
            const zoom = Math.max(map.getZoom() - minimapZoomOut, 0)

            for (const minimap of minimaps) {
                minimap.setView(center, zoom)
            }
        }

        // On map zoomend, update the available overlays
        const onMapZoomEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            const currentViewAreaSize = map.getBounds().getSize()

            for (const overlayCheckbox of overlayCheckboxes) {
                const areaMaxSize = overlayCheckbox.dataset.areaMaxSize
                if (!areaMaxSize) continue // Some overlays are always available

                const isAvailable = currentViewAreaSize <= areaMaxSize
                if (isAvailable) {
                    if (overlayCheckbox.disabled) {
                        overlayCheckbox.disabled = false
                        Tooltip.getOrCreateInstance(overlayCheckbox).disable()
                        // TODO: will it hide if needed?

                        // Restore the overlay state if it was checked before
                        if (overlayCheckbox.dataset.wasChecked) {
                            overlayCheckbox.dataset.wasChecked = undefined
                            overlayCheckbox.checked = true
                            overlayCheckbox.dispatchEvent(new Event("change"))
                        }
                    }
                } else {
                    // biome-ignore lint/style/useCollapsedElseIf: Readability
                    if (!overlayCheckbox.disabled) {
                        overlayCheckbox.disabled = true
                        Tooltip.getOrCreateInstance(overlayCheckbox).enable()
                        // TODO: will it hide if needed?

                        // Force uncheck the overlay when it becomes unavailable
                        if (overlayCheckbox.checked) {
                            overlayCheckbox.dataset.wasChecked = true
                            overlayCheckbox.checked = false
                            overlayCheckbox.dispatchEvent(new Event("change"))
                        }
                    }
                }
            }
        }

        // On layer click, update the active (base) layer
        const onBaseLayerClick = (e) => {
            const layerContainer = e.currentTarget
            const layerId = layerContainer.dataset.layerId
            const layer = getBaseLayerById(layerId)
            if (!layer) throw new Error(`Base layer ${layerId} not found`)

            const activeLayerId = map.getBaseLayerId()

            // Skip updates if the layer is already active
            if (layerId === activeLayerId) return

            // Remove all base layers
            map.eachLayer((layer) => {
                if (getBaseLayerById(layer.options.layerId)) map.removeLayer(layer)
            })

            // Add the new base layer
            map.addLayer(layer)

            // Trigger the baselayerchange event
            // https://leafletjs.com/reference.html#map-baselayerchange
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("baselayerchange", { layer, name: layerId })
        }

        // On overlay checkbox change, add or remove the overlay layer
        const onOverlayCheckboxChange = (e) => {
            const overlayCheckbox = e.currentTarget
            const layerId = overlayCheckbox.dataset.layerId
            const layer = getOverlayLayerById(layerId)
            if (!layer) throw new Error(`Overlay ${layerId} not found`)

            const checked = overlayCheckbox.checked
            const containsLayer = map.hasLayer(layer)

            // Skip updates if the layer is already in the correct state
            if (checked === containsLayer) return

            // Add or remove the overlay layer
            if (checked) {
                map.addLayer(layer)

                // Trigger the overlayadd event
                // https://leafletjs.com/reference.html#map-overlayadd
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayadd", { layer: layer, name: layerId })
            } else {
                map.removeLayer(layer)

                // Trigger the overlayremove event
                // https://leafletjs.com/reference.html#map-overlayremove
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayremove", { layer: layer, name: layerId })
            }
        }

        // On sidebar shown, update the minimaps view instantly
        const onInputCheckedChange = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

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
        input.addEventListener("change", onInputCheckedChange)

        return container
    }
}
