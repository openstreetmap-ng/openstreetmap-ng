import * as L from "leaflet"
import { getBaseLayerById } from "./_osm.js"
import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"

const MINIMAP_ZOOM_OUT = 2

export const getLayersSidebarToggleButton = (options) => {
    const control = getSidebarToggleButton(options, "layers", "javascripts.map.layers.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const input = control.input

        const layerContainers = sidebar.querySelectorAll(".layer")
        const minimaps = []

        // TODO: invalidateSize ?

        // Initialize the minimap
        for (const layerContainer of layerContainers) {
            const layerId = layerContainer.dataset.layerId
            const layer = getBaseLayerById(layerId)

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
            const zoom = Math.max(map.getZoom() - MINIMAP_ZOOM_OUT, 0)

            for (const minimap of minimaps) {
                minimap.setView(center, zoom)
            }
        }

        // On layer click, update the active (base) layer
        const onLayerClick = (e) => {
            const layerContainer = e.currentTarget
            const layerId = layerContainer.dataset.layerId
            const activeLayerId = map.getBaseLayerId()

            // Skip updates if the layer is already active
            if (layerId === activeLayerId) return

            // Remove all base layers
            map.eachLayer((layer) => {
                if (getBaseLayerById(layer.options.layerId)) map.removeLayer(layer)
            })

            // Add the new base layer
            const layer = getBaseLayerById(layerId)
            map.addLayer(layer)

            // Trigger the baselayerchange event
            // https://leafletjs.com/reference.html#map-baselayerchange
            // https://leafletjs.com/reference.html#layerscontrolevent
            map.fire("baselayerchange", { layer, name: layerId })
        }

        // On sidebar shown, update the minimaps view instantly
        const onInputCheckedChange = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            const center = map.getCenter()
            const zoom = Math.max(map.getZoom() - MINIMAP_ZOOM_OUT, 0)

            for (const minimap of minimaps) {
                minimap.setView(center, zoom, { animate: false })
            }
        }

        // Listen for events
        map.addEventListener("baselayerchange", onBaseLayerChange)
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        for (const layerContainer of layerContainers) layerContainer.addEventListener("click", onLayerClick)
        input.addEventListener("change", onInputCheckedChange)

        return container
    }
}
