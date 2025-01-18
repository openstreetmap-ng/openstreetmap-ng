import { Tooltip } from "bootstrap"
import { type FlyToOptions, type JumpToOptions, Map as MaplibreMap } from "maplibre-gl"
import { mapQueryAreaMaxSize, noteQueryAreaMaxSize } from "../_config"
import { getMapOverlayOpacity } from "../_local-storage"
import {
    addLayerEventHandler,
    addMapLayer,
    addMapLayerSources,
    hasMapLayer,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "./_layers.ts"
import { getMapBaseLayerId } from "./_map-utils.ts"
import { SidebarToggleControl } from "./_sidebar-toggle-button.ts"
import { configureDefaultMapBehavior, getLngLatBoundsSize } from "./_utils"

const minimapZoomOut = 2

export class LayersSidebarToggleControl extends SidebarToggleControl {
    constructor() {
        super("layers", "javascripts.map.layers.title")
    }

    public onAdd(map: MaplibreMap): HTMLElement {
        const container = super.onAdd(map)
        const button = container.querySelector("button")

        const minimaps: MaplibreMap[] = []
        const layerIdContainerMap: Map<LayerId, HTMLElement> = new Map()
        for (const container of [
            ...this.sidebar.querySelectorAll("div.base.layer"),
            ...this.sidebar.querySelectorAll("div.overlay.layer"),
        ]) {
            const layerId = container.dataset.layerId as LayerId
            layerIdContainerMap.set(layerId, container)
        }
        const overlayOpacityRange = this.sidebar.querySelector("input.overlay-opacity")
        overlayOpacityRange.value = (getMapOverlayOpacity() * 100).toString()
        const layerIdOverlayCheckboxMap: Map<LayerId, HTMLInputElement> = new Map()
        for (const overlayCheckbox of this.sidebar.querySelectorAll("input.overlay")) {
            layerIdOverlayCheckboxMap.set(overlayCheckbox.value as LayerId, overlayCheckbox)
        }

        /** Ensure minimaps have been initialized */
        let initializeMinimapsOnce = (): void => {
            for (const container of layerIdContainerMap.values()) {
                const layerId = container.dataset.layerId as LayerId
                const layerConfig = layersConfig.get(layerId)
                if (!layerConfig) {
                    console.error("Minimap layer", layerId, "not found")
                    continue
                }

                console.debug("Initializing minimap layer", layerId)
                const minimapContainer = container.querySelector("div.leaflet-container")
                const minimap = new MaplibreMap({
                    container: minimapContainer,
                    attributionControl: false,
                    interactive: false,
                    refreshExpiredTiles: false,
                })
                configureDefaultMapBehavior(minimap)
                addMapLayerSources(minimap, layerConfig.isBaseLayer ? "base" : "all")
                addMapLayer(minimap, layerId, null, false)
                // TODO: leaflet leftover: opacity 1
                minimaps.push(minimap)
            }

            initializeMinimapsOnce = () => {}
        }

        // On sidebar shown, update the sidebar state
        button.addEventListener("click", () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            initializeMinimapsOnce()
            const options: JumpToOptions = {
                center: map.getCenter(),
                zoom: Math.max(map.getZoom() - minimapZoomOut, 0),
            }
            for (const minimap of minimaps) {
                minimap.resize()
                minimap.jumpTo(options)
            }
            updateAvailableOverlays()
        })

        // On layer change, update the sidebar
        addLayerEventHandler((isAdded, layerId) => {
            const container = layerIdContainerMap.get(layerId)
            if (container) {
                container.classList.toggle("active", isAdded)
            } else {
                // No container found, maybe it's a checkbox
                const checkbox = layerIdOverlayCheckboxMap.get(layerId)
                if (!checkbox || checkbox.checked === isAdded) return
                checkbox.checked = isAdded
                checkbox.dispatchEvent(new Event("change"))
            }
        })

        // On map move, update the minimaps view
        map.on("moveend", () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const options: FlyToOptions = {
                center: map.getCenter(),
                zoom: Math.max(map.getZoom() - minimapZoomOut, 0),
            }
            for (const minimap of minimaps) {
                minimap.flyTo(options)
            }
        })

        /** On map zoom, update the available overlays */
        const updateAvailableOverlays = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const currentViewAreaSize = getLngLatBoundsSize(map.getBounds())

            for (const [layerId, areaMaxSize] of [
                ["notes", noteQueryAreaMaxSize],
                ["data", mapQueryAreaMaxSize],
            ] as [LayerId, number][]) {
                const checkbox = layerIdOverlayCheckboxMap.get(layerId)
                const isAvailable = currentViewAreaSize <= areaMaxSize
                if (isAvailable) {
                    if (checkbox.disabled) {
                        checkbox.disabled = false

                        const parent = checkbox.closest(".form-check") as HTMLElement
                        parent.classList.remove("disabled")
                        parent.ariaDisabled = "false"
                        const tooltip = Tooltip.getInstance(parent)
                        tooltip.disable()
                        tooltip.hide()

                        // Restore the overlay state if it was checked before
                        if (checkbox.dataset.wasChecked) {
                            console.debug("Restoring checked state for overlay", layerId)
                            checkbox.dataset.wasChecked = undefined
                            checkbox.checked = true
                            checkbox.dispatchEvent(new Event("change"))
                        }
                    }
                } else if (!checkbox.disabled) {
                    checkbox.blur()
                    checkbox.disabled = true

                    const parent = checkbox.closest(".form-check") as HTMLElement
                    parent.classList.add("disabled")
                    parent.ariaDisabled = "true"
                    Tooltip.getOrCreateInstance(parent, {
                        title: parent.dataset.bsTitle,
                        placement: "left",
                    }).enable()

                    // Force uncheck the overlay when it becomes unavailable
                    if (checkbox.checked) {
                        console.debug("Forcing unchecked state for overlay", layerId)
                        checkbox.dataset.wasChecked = "true"
                        checkbox.checked = false
                        checkbox.dispatchEvent(new Event("change"))
                    }
                }
            }
        }
        map.on("zoomend", updateAvailableOverlays)

        /** On layer click, update the active (base) layer */
        const onContainerClick = (e: MouseEvent) => {
            const container = e.currentTarget as HTMLElement
            const layerId = container.dataset.layerId as LayerId
            const config = layersConfig.get(layerId)

            if (config.isBaseLayer) {
                // Skip updates if the container is already active
                if (container.classList.contains("active")) return
                const activeLayerId = getMapBaseLayerId(map)
                if (activeLayerId) removeMapLayer(map, activeLayerId)
                addMapLayer(map, layerId)
            } else {
                const checked = !container.classList.contains("active")
                container.classList.toggle("active", checked)
                if (checked) {
                    addMapLayer(map, layerId)
                } else {
                    removeMapLayer(map, layerId)
                }
            }
        }
        for (const container of layerIdContainerMap.values()) {
            container.addEventListener("click", onContainerClick)
        }

        /** On overlay checkbox change, add or remove the overlay layer */
        const onOverlayCheckboxChange = (e: Event) => {
            const checkbox = e.currentTarget as HTMLInputElement
            const layerId = checkbox.value as LayerId
            const checked = checkbox.checked

            // Skip updates if the layer is already in the correct state
            if (checked === hasMapLayer(map, layerId)) {
                console.warn("Overlay layer", layerId, "is already", checked ? "added" : "removed")
                return
            }

            if (checked) {
                addMapLayer(map, layerId)
            } else {
                removeMapLayer(map, layerId)
            }
        }
        for (const overlayCheckbox of layerIdOverlayCheckboxMap.values()) {
            overlayCheckbox.addEventListener("change", onOverlayCheckboxChange)
        }

        // On overlay opacity change, update the layer and remember the new value
        // TODO: leaflet leftover
        // overlayOpacityRange.addEventListener(
        //     "input",
        //     throttle(({ target }) => {
        //         const overlayOpacity = Number.parseFloat((target as HTMLInputElement).value) / 100
        //         setMapOverlayOpacity(overlayOpacity)
        //         for (const overlayContainer of overlayContainers) {
        //             const layer = getOverlayLayerById(overlayContainer.dataset.layerId as LayerId) as L.TileLayer
        //             layer.setOpacity(overlayOpacity)
        //         }
        //     }, 50),
        // )

        return container
    }
}
