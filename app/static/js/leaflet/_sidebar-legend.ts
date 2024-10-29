import { Tooltip } from "bootstrap"
import i18next from "i18next"
import type * as L from "leaflet"
import type { LayerId } from "./_layers"
import { getMapBaseLayerId } from "./_map-utils"
import { type SidebarToggleControl, getSidebarToggleButton } from "./_sidebar-toggle-button"

const precomputeMaxZoom = 25

export const getLegendSidebarToggleButton = (): SidebarToggleControl => {
    const control = getSidebarToggleButton("legend", "javascripts.key.tooltip")
    const controlOnAdd = control.onAdd

    control.onAdd = (map: L.Map): HTMLElement => {
        const container = controlOnAdd(map)
        const button = container.querySelector("button")

        // Discover the legend items and precompute their visibility
        const sidebar = control.sidebar
        const layerElementsMap: Map<LayerId, { element: HTMLTableRowElement; visibility: boolean[] }[]> = new Map()
        const layerContainers = sidebar.querySelectorAll("table.layer-container")
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

        // On sidebar shown, update the legend (simulate zoomend)
        button.addEventListener("click", () => {
            if (button.classList.contains("active")) onZoomEnd()
        })

        // On base layer change, update availability of the button and its tooltip
        map.addEventListener("baselayerchange", () => {
            const activeLayerId = getMapBaseLayerId(map)
            const isLegendAvailable = layerElementsMap.has(activeLayerId)

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

        /** On zoomend, display only related elements */
        const onZoomEnd = (): void => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const activeLayerId = getMapBaseLayerId(map)
            const currentZoom = Math.floor(map.getZoom())

            for (const layerContainer of layerContainers) {
                const layerId = layerContainer.dataset.layerId as LayerId
                if (layerId === activeLayerId) {
                    // Show section
                    layerContainer.classList.remove("d-none")

                    // Update visibility of elements
                    // TODO: map key not available for this layer
                    for (const { element, visibility } of layerElementsMap.get(layerId)) {
                        const isVisible = visibility[currentZoom]
                        element.classList.toggle("d-none", !isVisible)
                    }
                } else {
                    // Hide section
                    layerContainer.classList.add("d-none")
                }
            }
        }
        map.addEventListener("zoomend", onZoomEnd)

        return container
    }

    return control
}
