import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"

const availableLegends = ["mapnik", "cyclemap"]
const precomputeMaxZoom = 25

export const getLegendSidebarToggleButton = (options) => {
    const control = getSidebarToggleButton(options, "legend", "javascripts.key.tooltip")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const input = control.input
        const tooltip = control.tooltip

        // Discover the legend items and precompute their visibility
        const layerContainers = sidebar.querySelectorAll(".layer-container")
        const layerElementsMap = layerContainers.reduce((result, layerContainer) => {
            const layer = layerContainer.dataset.layer
            const elements = layerContainer.querySelectorAll(".legend-item").map((element) => {
                const minZoom = parseFloat(element.dataset.minZoom)
                const maxZoom = parseFloat(element.dataset.maxZoom)
                const visibility = new Array(precomputeMaxZoom + 1)

                visibility.fill(false, 0, minZoom)
                visibility.fill(true, minZoom, maxZoom + 1)
                visibility.fill(false, maxZoom + 1)

                return { element, visibility }
            })

            result[layer] = elements
            return result
        }, {})

        // On layer change, update availability of the button and its tooltip
        const onBaseLayerChange = () => {
            const layer = map.getMapBaseLayerId()
            const isLegendAvailable = availableLegends.includes(layer)

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

            const activeLayer = map.getMapBaseLayerId()
            const currentZoom = Math.floor(map.getZoom())

            for (const layerContainer of layerContainers) {
                const layer = layerContainer.dataset.layer
                if (layer === activeLayer) {
                    // Show section
                    layerContainer.classList.remove("d-none")

                    // Update visibility of elements
                    for (const { element, visibility } of layerElementsMap[layer]) {
                        const isVisible = visibility[currentZoom]
                        if (isVisible) {
                            element.classList.remove("d-none")
                        } else {
                            element.classList.add("d-none")
                        }
                    }
                } else {
                    // Hide section
                    layerContainer.classList.add("d-none")
                }
            }
        }

        // On input checked, update the legend (simulate zoomend)
        const inputOnChange = () => {
            if (input.checked) onZoomEnd()
        }

        // Listen for events
        map.addEventListener("baselayerchange", onBaseLayerChange)
        map.addEventListener("zoomend", onZoomEnd)
        input.addEventListener("change", inputOnChange)

        // Initial update
        onBaseLayerChange()

        return container
    }
}
