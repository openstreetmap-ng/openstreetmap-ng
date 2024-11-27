import { Tooltip } from "bootstrap"
import * as L from "leaflet"
import { mapQueryAreaMaxSize, noteQueryAreaMaxSize } from "../_config"
import { getOverlayOpacity, setOverlayOpacity } from "../_local-storage"
import { throttle } from "../_utils"
import { type LayerId, getBaseLayerById, getLayerData, getOverlayLayerById } from "./_layers"
import { cloneTileLayer, getMapBaseLayerId } from "./_map-utils"
import { type SidebarToggleControl, getSidebarToggleButton } from "./_sidebar-toggle-button"
import { getLatLngBoundsSize } from "./_utils"

const minimapZoomOut = 2

export const getLayersSidebarToggleButton = (): SidebarToggleControl => {
    const control = getSidebarToggleButton("layers", "javascripts.map.layers.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map: L.Map): HTMLElement => {
        const container = controlOnAdd(map)
        const button = container.querySelector("button")

        const minimaps: L.Map[] = []
        const sidebar = control.sidebar
        const layerContainers = sidebar.querySelectorAll("div.base.layer")
        const overlayContainers = sidebar.querySelectorAll("div.overlay.layer")
        const layerIdOverlayContainerMap: Map<LayerId, HTMLElement> = new Map()
        for (const overlayContainer of overlayContainers) {
            layerIdOverlayContainerMap.set(overlayContainer.dataset.layerId as LayerId, overlayContainer)
        }
        const overlayOpacityRange = sidebar.querySelector("input.overlay-opacity")
        overlayOpacityRange.value = (getOverlayOpacity() * 100).toString()
        const overlayCheckboxes = sidebar.querySelectorAll("input.overlay")
        const layerIdOverlayCheckboxMap: Map<LayerId, HTMLInputElement> = new Map()
        for (const overlayCheckbox of overlayCheckboxes) {
            layerIdOverlayCheckboxMap.set(overlayCheckbox.value as LayerId, overlayCheckbox)
        }

        /** Ensure minimaps have been initialized */
        const ensureMinimapsInitialized = (): void => {
            if (minimaps.length) return

            for (const container of [...layerContainers, ...overlayContainers]) {
                const layerId = container.dataset.layerId as LayerId
                const layer = getBaseLayerById(layerId) ?? (getOverlayLayerById(layerId) as L.TileLayer)
                if (!layer) {
                    console.error("Minimap layer", layerId, "not found")
                    continue
                }

                console.debug("Initializing minimap for layer", layerId)
                const minimapContainer = container.querySelector("div.leaflet-container")
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

                const cloneLayer = cloneTileLayer(layer)
                cloneLayer.setOpacity(1)
                minimap.addLayer(cloneLayer)
                minimaps.push(minimap)
            }
        }

        // On sidebar shown, update the sidebar state
        button.addEventListener("click", () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            ensureMinimapsInitialized()
            const center = map.getCenter()
            const zoom = Math.max(map.getZoom() - minimapZoomOut, 0)

            for (const minimap of minimaps) {
                minimap.setView(center, zoom, { animate: false })
            }

            onMapZoomEnd()
        })

        // On base layer change, update the active container
        map.addEventListener("baselayerchange", () => {
            const activeLayerId = getMapBaseLayerId(map)
            for (const container of layerContainers) {
                const layerId = container.dataset.layerId
                container.classList.toggle("active", layerId === activeLayerId)
            }
        })

        // On overlay layer add, select the corresponding container/checkbox
        map.addEventListener("overlayadd", ({ name }) => {
            const overlayContainer = layerIdOverlayContainerMap.get(name as LayerId)
            overlayContainer?.classList.add("active")
            const overlayCheckbox = layerIdOverlayCheckboxMap.get(name as LayerId)
            if (overlayCheckbox && overlayCheckbox.checked !== true) {
                overlayCheckbox.checked = true
                overlayCheckbox.dispatchEvent(new Event("change"))
            }
        })

        // On overlay layer remove, unselect the corresponding container/checkbox
        map.addEventListener("overlayremove", ({ name }) => {
            const overlayContainer = layerIdOverlayContainerMap.get(name as LayerId)
            overlayContainer?.classList.remove("active")
            const overlayCheckbox = layerIdOverlayCheckboxMap.get(name as LayerId)
            if (overlayCheckbox && overlayCheckbox.checked !== false) {
                overlayCheckbox.checked = false
                overlayCheckbox.dispatchEvent(new Event("change"))
            }
        })

        // On map zoomend or moveend, update the minimaps view
        map.addEventListener("zoomend moveend", () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const center = map.getCenter()
            const zoom = Math.max(map.getZoom() - minimapZoomOut, 0)
            for (const minimap of minimaps) {
                minimap.setView(center, zoom)
            }
        })

        /** On map zoomend, update the available overlays */
        const onMapZoomEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const currentViewAreaSize = getLatLngBoundsSize(map.getBounds())

            for (const [layerId, areaMaxSize] of [
                ["notes", noteQueryAreaMaxSize],
                ["data", mapQueryAreaMaxSize],
            ] as [LayerId, number][]) {
                const overlayCheckbox = layerIdOverlayCheckboxMap.get(layerId)
                const isAvailable = currentViewAreaSize <= areaMaxSize
                if (isAvailable) {
                    if (overlayCheckbox.disabled) {
                        overlayCheckbox.disabled = false

                        const parent = overlayCheckbox.closest(".form-check") as HTMLElement
                        parent.classList.remove("disabled")
                        parent.ariaDisabled = "false"
                        const tooltip = Tooltip.getInstance(parent)
                        tooltip.disable()
                        tooltip.hide()

                        // Restore the overlay state if it was checked before
                        if (overlayCheckbox.dataset.wasChecked) {
                            console.debug("Restoring checked state for overlay", layerId)
                            overlayCheckbox.dataset.wasChecked = undefined
                            overlayCheckbox.checked = true
                            overlayCheckbox.dispatchEvent(new Event("change"))
                        }
                    }
                } else if (!overlayCheckbox.disabled) {
                    overlayCheckbox.blur()
                    overlayCheckbox.disabled = true

                    const parent = overlayCheckbox.closest(".form-check") as HTMLElement
                    parent.classList.add("disabled")
                    parent.ariaDisabled = "true"
                    Tooltip.getOrCreateInstance(parent, {
                        title: parent.dataset.bsTitle,
                        placement: "left",
                    }).enable()

                    // Force uncheck the overlay when it becomes unavailable
                    if (overlayCheckbox.checked) {
                        console.debug("Forcing unchecked state for overlay", layerId)
                        overlayCheckbox.dataset.wasChecked = "true"
                        overlayCheckbox.checked = false
                        overlayCheckbox.dispatchEvent(new Event("change"))
                    }
                }
            }
        }
        map.addEventListener("zoomend", onMapZoomEnd)

        /** On layer click, update the active (base) layer */
        const onBaseLayerClick = (e: Event) => {
            const layerContainer = e.currentTarget as HTMLElement
            const layerId = layerContainer.dataset.layerId as LayerId
            const layer = getBaseLayerById(layerId)
            if (!layer) {
                console.error("Base layer", layerId, "not found")
                return
            }

            // Skip updates if the layer is already active
            const activeLayerId = getMapBaseLayerId(map)
            if (layerId === activeLayerId) return

            // Remove all base layers
            map.eachLayer((layer) => {
                const data = getLayerData(layer)
                if (data && getBaseLayerById(data.layerId)) {
                    console.debug("Removing base layer", data.layerId)
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
        for (const layerContainer of layerContainers) {
            layerContainer.addEventListener("click", onBaseLayerClick)
        }

        const onOverlayLayerClick = (e: Event) => {
            const layerContainer = e.currentTarget as HTMLElement
            const layerId = layerContainer.dataset.layerId as LayerId
            const layer = getOverlayLayerById(layerId)
            if (!layer) {
                console.error("Overlay layer", layerId, "not found")
                return
            }

            const checked = !layerContainer.classList.contains("active")
            const containsLayer = map.hasLayer(layer)

            // Skip updates if the layer is already in the correct state
            layerContainer.classList.toggle("active")
            if (checked === containsLayer) {
                console.warn("Overlay layer", layerId, "is already", checked ? "added" : "removed")
                return
            }

            // Add or remove the overlay layer
            if (checked) {
                console.debug("Adding overlay layer", layerId)
                map.addLayer(layer)

                // Trigger the overlayadd event
                // https://leafletjs.com/reference.html#map-overlayadd
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayadd", { layer, name: layerId })
            } else {
                console.debug("Removing overlay layer", layerId)
                map.removeLayer(layer)

                // Trigger the overlayremove event
                // https://leafletjs.com/reference.html#map-overlayremove
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayremove", { layer, name: layerId })
            }
        }
        for (const overlayContainer of overlayContainers) {
            overlayContainer.addEventListener("click", onOverlayLayerClick)
        }

        /** On overlay checkbox change, add or remove the overlay layer */
        const onOverlayCheckboxChange = (e: Event) => {
            const overlayCheckbox = e.currentTarget as HTMLInputElement
            const layerId = overlayCheckbox.value as LayerId
            const layer = getOverlayLayerById(layerId)
            if (!layer) {
                console.error("Overlay layer", layerId, "not found")
                return
            }

            const checked = overlayCheckbox.checked
            const containsLayer = map.hasLayer(layer)

            // Skip updates if the layer is already in the correct state
            if (checked === containsLayer) {
                console.warn("Overlay layer", layerId, "is already", checked ? "added" : "removed")
                return
            }

            // Add or remove the overlay layer
            if (checked) {
                console.debug("Adding overlay layer", layerId)
                map.addLayer(layer)

                // Trigger the overlayadd event
                // https://leafletjs.com/reference.html#map-overlayadd
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayadd", { layer, name: layerId })
            } else {
                console.debug("Removing overlay layer", layerId)
                map.removeLayer(layer)

                // Trigger the overlayremove event
                // https://leafletjs.com/reference.html#map-overlayremove
                // https://leafletjs.com/reference.html#layerscontrolevent
                map.fire("overlayremove", { layer, name: layerId })
            }
        }
        for (const overlayCheckbox of overlayCheckboxes) {
            overlayCheckbox.addEventListener("change", onOverlayCheckboxChange)
        }

        // On overlay opacity change, update the layer and remember the new value
        overlayOpacityRange.addEventListener(
            "input",
            throttle(({ target }) => {
                const overlayOpacity = Number.parseFloat((target as HTMLInputElement).value) / 100
                setOverlayOpacity(overlayOpacity)
                for (const overlayContainer of overlayContainers) {
                    const layer = getOverlayLayerById(overlayContainer.dataset.layerId as LayerId) as L.TileLayer
                    layer.setOpacity(overlayOpacity)
                }
            }, 50),
        )

        return container
    }

    return control
}
