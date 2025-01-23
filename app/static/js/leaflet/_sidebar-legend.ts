import { Tooltip } from "bootstrap"
import i18next from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { type LayerId, addLayerEventHandler } from "./_layers"
import { getMapBaseLayerId } from "./_map-utils"
import { SidebarToggleControl } from "./_sidebar-toggle-button"

const precomputeMaxZoom = 25

export class LegendSidebarToggleControl extends SidebarToggleControl {
    public _container: HTMLElement

    public constructor() {
        super("legend", "javascripts.key.tooltip")
    }

    public override onAdd(map: MaplibreMap): HTMLElement {
        const container = super.onAdd(map)
        const button = container.querySelector("button")

        // On sidebar shown, update the sidebar
        button.addEventListener("click", () => {
            if (button.classList.contains("active")) updateSidebar()
        })

        // Discover the legend items and precompute their visibility
        const layerElementsMap = new Map<LayerId, { element: HTMLTableRowElement; visibility: boolean[] }[]>()
        const layerContainers = this.sidebar.querySelectorAll("table.layer-container")
        for (const layerContainer of layerContainers) {
            const layerId = layerContainer.dataset.layerId as LayerId
            const elements = Array.from(layerContainer.querySelectorAll("tr")).map((element) => {
                const [minZoomStr, maxZoomStr] = element.dataset.zoom.split("-")
                const minZoom = minZoomStr ? Number.parseInt(minZoomStr, 10) : 0
                const maxZoom = maxZoomStr ? Number.parseInt(maxZoomStr, 10) : precomputeMaxZoom
                const visibility: boolean[] = new Array(precomputeMaxZoom + 1)

                visibility.fill(false, 0, minZoom)
                visibility.fill(true, minZoom, maxZoom + 1)
                visibility.fill(false, maxZoom + 1)

                return { element, visibility }
            })
            layerElementsMap.set(layerId, elements)
        }

        // On base layer change, update availability of the button and its tooltip
        addLayerEventHandler((isAdded, layerId, config) => {
            if (!isAdded || !config.isBaseLayer) return
            const isLegendAvailable = layerElementsMap.has(layerId)
            if (isLegendAvailable) {
                if (button.disabled) {
                    button.disabled = false
                    Tooltip.getInstance(button).setContent({
                        ".tooltip-inner": i18next.t("javascripts.key.tooltip"),
                    })
                }
            } else {
                if (!button.disabled) {
                    button.blur()
                    button.disabled = true
                    Tooltip.getInstance(button).setContent({
                        ".tooltip-inner": i18next.t("javascripts.key.tooltip_disabled"),
                    })
                }

                // Uncheck the input if checked
                if (button.classList.contains("active")) {
                    button.dispatchEvent(new Event("click"))
                }
            }
        })

        /** Update the sidebar content to show only relevant elements */
        const updateSidebar = (): void => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const activeLayerId = getMapBaseLayerId(map)
            const currentZoomFloor = map.getZoom() | 0

            for (const layerContainer of layerContainers) {
                const layerId = layerContainer.dataset.layerId as LayerId
                if (layerId === activeLayerId) {
                    // Show section
                    layerContainer.classList.remove("d-none")

                    // Update visibility of elements
                    // TODO: map key not available for this layer infobox
                    for (const { element, visibility } of layerElementsMap.get(layerId)) {
                        const isVisible = visibility[currentZoomFloor]
                        element.classList.toggle("d-none", !isVisible)
                    }
                } else {
                    // Hide section
                    layerContainer.classList.add("d-none")
                }
            }
        }
        map.on("zoomend", updateSidebar)

        this._container = container
        return container
    }
}
