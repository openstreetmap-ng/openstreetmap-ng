import { SidebarToggleControl } from "@index/sidebar/_toggle-button"
import { config, isMobile } from "@lib/config"
import {
    globeProjectionStorage,
    layerOrderStorage,
    overlayOpacityStorage,
} from "@lib/local-storage"
import { getLngLatBoundsSize } from "@lib/map/bounds"
import { configureDefaultMapBehavior } from "@lib/map/defaults"
import {
    addLayerEventHandler,
    addMapLayer,
    addMapLayerSources,
    hasMapLayer,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "@lib/map/layers/layers"
import { getMapBaseLayerId } from "@lib/map/state"
import { memoize } from "@lib/memoize"
import { throttle } from "@lib/throttle"
import { Tooltip } from "bootstrap"
import { type EaseToOptions, type JumpToOptions, Map as MaplibreMap } from "maplibre-gl"

const MINIMAP_ZOOM_OUT = 2

export class LayerSidebarToggleControl extends SidebarToggleControl {
    public _container: HTMLElement

    public constructor() {
        super("layers", "javascripts.map.layers.title")
    }

    public override onAdd(map: MaplibreMap): HTMLElement {
        const container = super.onAdd(map)
        const button = container.querySelector("button")

        const minimaps: MaplibreMap[] = []
        const layerIdContainerMap = new Map<LayerId, HTMLElement>()
        for (const container of [
            ...this.sidebar.querySelectorAll(".base.layer"),
            ...this.sidebar.querySelectorAll(".overlay.layer"),
        ] as HTMLElement[]) {
            const layerId = container.dataset.layerId as LayerId
            layerIdContainerMap.set(layerId, container)
        }
        const layerIdOverlayCheckboxMap = new Map<LayerId, HTMLInputElement>()
        for (const overlayCheckbox of this.sidebar.querySelectorAll("input.overlay")) {
            layerIdOverlayCheckboxMap.set(
                overlayCheckbox.value as LayerId,
                overlayCheckbox,
            )
        }

        /** Ensure minimaps have been initialized */
        const initializeMinimapsOnce = memoize((): void => {
            for (const container of layerIdContainerMap.values()) {
                const layerId = container.dataset.layerId as LayerId
                const layerConfig = layersConfig.get(layerId)
                if (!layerConfig) {
                    console.error("Minimap layer", layerId, "not found")
                    continue
                }

                const minimapContainer = container.querySelector("div.map-container")

                // On mobile devices, show thumbnail instead of initializing MapLibre
                // Avoids "Too many active WebGL context even after destroyed"
                if (container.dataset.thumbnail && isMobile()) {
                    console.debug("Showing layer thumbnail", layerId)
                    minimapContainer.innerHTML = `<img src="${container.dataset.thumbnail}" loading="lazy">`
                    continue
                }

                console.debug("Initializing minimap layer", layerId)
                const minimap = new MaplibreMap({
                    container: minimapContainer,
                    attributionControl: false,
                    interactive: false,
                    refreshExpiredTiles: false,
                })
                configureDefaultMapBehavior(minimap)
                addMapLayerSources(minimap, layerId)
                addMapLayer(minimap, layerId, false)
                if (!layerConfig.isBaseLayer)
                    minimap.setPaintProperty(layerId, "raster-opacity", 1)
                minimaps.push(minimap)
            }
        })

        const layerOrderContainer = this.sidebar.querySelector(".layer-order")
        const layerOrderItems = layerOrderContainer.querySelector("ul")
        const layerCollapseButton = layerOrderContainer.querySelector("button")
        layerCollapseButton.addEventListener("click", () => {
            layerOrderContainer.classList.toggle("collapsed")
        })

        const updateLayerOrder = (selectedLayerId?: LayerId) => {
            let order = layerOrderStorage.get() || []

            if (selectedLayerId && selectedLayerId !== "standard") {
                // Create a new order with the selected layer upfront
                order = [
                    selectedLayerId,
                    ...order.filter((id) => id !== selectedLayerId),
                ]
                layerOrderStorage.set(order)
            }

            for (const layerId of order.reverse()) {
                const container = layerIdContainerMap.get(layerId)
                if (container) layerOrderItems.prepend(container)
            }
        }

        // On sidebar shown, update the sidebar state
        button.addEventListener("click", () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            initializeMinimapsOnce()
            const options: JumpToOptions = {
                center: map.getCenter(),
                zoom: Math.max(map.getZoom() - MINIMAP_ZOOM_OUT, 0),
            }
            for (const minimap of minimaps) {
                minimap.resize()
                minimap.jumpTo(options)
            }
            updateLayerOrder()
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

            const options: EaseToOptions = {
                center: map.getCenter(),
                zoom: Math.max(map.getZoom() - MINIMAP_ZOOM_OUT, 0),
            }
            for (const minimap of minimaps) {
                minimap.easeTo(options)
            }
        })

        /** On map zoom, update the available overlays */
        const updateAvailableOverlays = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const currentViewAreaSize = getLngLatBoundsSize(map.getBounds())

            for (const [layerId, areaMaxSize] of [
                ["notes", config.noteQueryAreaMaxSize],
                ["data", config.mapQueryAreaMaxSize],
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
                            console.debug(
                                "Restoring checked state for overlay",
                                layerId,
                            )
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

        // Setup globe perspective checkbox
        const globeProjectionCheckbox = this.sidebar.querySelector(
            "input.globe-projection",
        )
        if (globeProjectionCheckbox) {
            // Handle checkbox changes
            globeProjectionCheckbox.addEventListener("change", () => {
                const enabled = globeProjectionCheckbox.checked
                globeProjectionStorage.set(enabled)
                const projection = { type: enabled ? "globe" : "mercator" }
                map.setProjection(projection)

                // Workaround a bug where after switching back to mercator,
                // the map is not fit to the screen (there is grey padding)
                if (!enabled) map.resize()
            })

            // Initialize checkbox state from local storage
            const enabled = globeProjectionStorage.get()
            if (enabled !== null && globeProjectionCheckbox.checked !== enabled) {
                console.debug("Setting globe projection checkbox to", enabled)
                globeProjectionCheckbox.checked = enabled
                globeProjectionCheckbox.dispatchEvent(new Event("change"))
            }
        }

        /** On layer click, update the active (base) layer */
        const onContainerClick = (e: MouseEvent) => {
            const container = e.currentTarget as HTMLElement
            const layerId = container.dataset.layerId as LayerId
            const config = layersConfig.get(layerId)

            if (config.isBaseLayer) {
                // Skip updates if the container is already active
                if (container.classList.contains("active")) return

                updateLayerOrder(layerId)
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
                console.debug(
                    "Overlay layer",
                    layerId,
                    "is already",
                    checked ? "added" : "removed",
                )
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

        for (const range of this.sidebar.querySelectorAll("input.overlay-opacity")) {
            const layerId = range.dataset.layerId as LayerId
            range.value = (overlayOpacityStorage(layerId).get() * 100).toString()
            range.addEventListener(
                "input",
                throttle(() => {
                    const opacity = Number.parseFloat(range.value) / 100
                    map.setPaintProperty(layerId, "raster-opacity", opacity)
                    overlayOpacityStorage(layerId).set(opacity)
                }, 100),
            )
        }

        this._container = container
        return container
    }
}

/** Toggle the spinner for the given layer */
export const toggleLayerSpinner = (layerName: LayerId, loading: boolean): void => {
    document
        .querySelector(`.leaflet-sidebar.layers input.overlay[value=${layerName}]`)
        .parentElement.querySelector(".spinner-border")
        .classList.toggle("d-none", !loading)
}
