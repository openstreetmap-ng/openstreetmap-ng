import i18next from "i18next"
import { getMapBaseLayerId } from "./_map-utils.js"
import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"

const precomputeMaxZoom = 25

export const getLegendSidebarToggleButton = () => {
    const control = getSidebarToggleButton("legend", "javascripts.key.tooltip")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const button = control.button
        const tooltip = control.tooltip

        // Discover the legend items and precompute their visibility
        const layerContainers = sidebar.querySelectorAll(".layer-container")
        const layerElementsMap = [...layerContainers].reduce((map, layerContainer) => {
            const layerId = layerContainer.dataset.layerId
            const elements = [...layerContainer.querySelectorAll("tr")].map((element) => {
                const [minZoomStr, maxZoomStr] = element.dataset.zoom.split("-")
                const minZoom = minZoomStr ? parseInt(minZoomStr, 10) : 0
                const maxZoom = maxZoomStr ? parseInt(maxZoomStr, 10) : precomputeMaxZoom
                const visibility = new Array(precomputeMaxZoom + 1)

                visibility.fill(false, 0, minZoom)
                visibility.fill(true, minZoom, maxZoom + 1)
                visibility.fill(false, maxZoom + 1)

                return { element, visibility }
            })

            return map.set(layerId, elements)
        }, new Map())

        // On layer change, update availability of the button and its tooltip
        const onBaseLayerChange = () => {
            const activeLayerId = getMapBaseLayerId(map)
            const isLegendAvailable = layerElementsMap.has(activeLayerId)

            if (isLegendAvailable) {
                if (button.disabled) {
                    button.disabled = false
                    tooltip.setContent({
                        ".tooltip-inner": i18next.t("javascripts.key.tooltip"),
                    })
                }
            } else {
                if (!button.disabled) {
                    button.blur()
                    button.disabled = true
                    tooltip.setContent({
                        ".tooltip-inner": i18next.t("javascripts.key.tooltip_disabled"),
                    })
                }

                // Uncheck the input if checked
                if (button.classList.contains("active")) {
                    button.dispatchEvent(new Event("click"))
                }
            }
        }

        // On zoom end, display only related elements
        const onZoomEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const activeLayerId = getMapBaseLayerId(map)
            const currentZoom = Math.floor(map.getZoom())

            for (const layerContainer of layerContainers) {
                const layerId = layerContainer.dataset.layerId
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

        // On sidebar shown, update the legend (simulate zoomend)
        const onButtonClick = () => {
            if (button.classList.contains("active")) onZoomEnd()
        }

        // Listen for events
        map.addEventListener("baselayerchange", onBaseLayerChange)
        map.addEventListener("zoomend", onZoomEnd)
        button.addEventListener("click", onButtonClick)

        return container
    }

    return control
}
