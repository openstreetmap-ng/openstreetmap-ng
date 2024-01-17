import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"
import { getMapBaseLayerId } from "./_utils.js"

const precomputeMaxZoom = 25

export const getLegendSidebarToggleButton = () => {
    const control = getSidebarToggleButton("legend", "javascripts.key.tooltip")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const input = control.input
        const tooltip = control.tooltip

        // Discover the legend items and precompute their visibility
        const layerContainers = sidebar.querySelectorAll(".layer-container")
        const layerElementsMap = layerContainers.reduce((map, layerContainer) => {
            const layerId = layerContainer.dataset.layerId
            const elements = layerContainer.querySelectorAll(".legend-item").map((element) => {
                const minZoom = parseFloat(element.dataset.minZoom)
                const maxZoom = parseFloat(element.dataset.maxZoom)
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
            const isLegendAvailable = layerElementsMap[activeLayerId] !== undefined

            if (isLegendAvailable) {
                if (input.disabled) {
                    input.disabled = false
                    tooltip.setContent({
                        ".tooltip-inner": I18n.t("javascripts.key.tooltip"),
                    })
                }
            } else {
                if (!input.disabled) {
                    input.disabled = true
                    tooltip.setContent({
                        ".tooltip-inner": I18n.t("javascripts.key.tooltip_disabled"),
                    })
                }

                // Uncheck the input if checked
                if (input.checked) {
                    input.checked = false
                    input.dispatchEvent(new Event("change"))
                }
            }
        }

        // On zoom end, display only related elements
        const onZoomEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            const activeLayerId = getMapBaseLayerId(map)
            const currentZoom = Math.floor(map.getZoom())

            for (const layerContainer of layerContainers) {
                const layerId = layerContainer.dataset.layerId
                if (layerId === activeLayerId) {
                    // Show section
                    layerContainer.classList.remove("d-none")

                    // Update visibility of elements
                    for (const { element, visibility } of layerElementsMap[layerId]) {
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
        const onInputCheckedChange = () => {
            if (input.checked) onZoomEnd()
        }

        // Listen for events
        map.addEventListener("baselayerchange", onBaseLayerChange)
        map.addEventListener("zoomend", onZoomEnd)
        input.addEventListener("change", onInputCheckedChange)

        // Initial update to set tooltip text
        onBaseLayerChange()

        return container
    }
}
