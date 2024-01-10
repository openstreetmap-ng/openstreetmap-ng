import * as L from "leaflet"
import { getGeoUri, getMapEmbedHtml, getMapShortUrl, getMapUrl } from "../_utils.js"
import { getOptimalExportParams } from "./_image-export.js"
import { getLocationFilter } from "./_location-filter.js"
import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"

export const getShareSidebarToggleButton = (options) => {
    const control = getSidebarToggleButton(options, "share", "javascripts.share.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const input = control.input

        const markerCheckbox = sidebar.querySelector(".marker-checkbox")
        const linkRadioInput = sidebar.querySelector(".link-button")
        const linkInput = sidebar.querySelector(".link-input")
        const shortLinkRadioInput = sidebar.querySelector(".short-link-button")
        const shortLinkInput = sidebar.querySelector(".short-link-input")
        const embedRadioInput = sidebar.querySelector(".embed-button")
        const embedInput = sidebar.querySelector(".embed-input")
        const geoUriLink = sidebar.querySelector(".geo-uri-link")
        const exportForm = sidebar.querySelector(".export-form")
        const exportFormatSelect = exportForm.querySelector(".export-format-select")
        const customRegionCheckbox = exportForm.querySelector(".custom-region-checkbox")
        const offsetsWithDetailRadioInputs = exportForm
            .querySelectorAll(".detail-input")
            .map((input) => [parseInt(input.value), input])

        // Null values until initialized
        let marker = null
        let locationFilter = null
        let optimalExportParams = null

        // TODO: in map object
        const getBaseLayer = () => {
            let baseLayer = null

            // Find the current base layer
            map.eachLayer((layer) => {
                if (map.baseLayers.has(layer)) {
                    baseLayer = layer
                }
            })

            if (!baseLayer) throw new Error("No base layer found")
            return baseLayer
        }

        const updateLinks = () => {
            const showMarker = markerCheckbox.checked

            if (linkRadioInput.checked) {
                const link = getMapUrl(map, showMarker)
                linkInput.value = link
            } else if (shortLinkRadioInput.checked) {
                const shortLink = getMapShortUrl(map, showMarker)
                shortLinkInput.value = shortLink
            } else if (embedRadioInput.checked) {
                const markerLatLng = showMarker ? marker.getLatLng() : null
                const embed = getMapEmbedHtml(map, markerLatLng)
                embedInput.value = embed
            }
        }

        const updateGeoUri = () => {
            const geoUri = getGeoUri(map)
            geoUriLink.href = geoUri
            geoUriLink.textContent = geoUri
        }

        // On map move, update marker position if marker is enabled
        const onMapMove = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return
            if (markerCheckbox.checked) {
                marker.setLatLng(map.getCenter())
            }
        }

        // On map move, update sidebar data
        const onMapMoveEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            updateLinks()
            updateGeoUri()
        }

        // On map zoomend or baselayerchange, update the optimal export params
        const onMapZoomOrLayerChange = () => {
            // Skip updates if the sidebar is hidden
            if (!input.checked) return

            const baseLayer = getBaseLayer()

            // Get the current base layer's min and max zoom
            const minZoom = baseLayer.options.minZoom
            const maxZoom = baseLayer.options.maxNativeZoom ?? baseLayer.options.maxZoom

            const bounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
            optimalExportParams = getOptimalExportParams(bounds)

            // Update the radio inputs availability
            for (const [zoomOffset, radioInput] of offsetsWithDetailRadioInputs) {
                const zoom = optimalExportParams.zoom + zoomOffset
                // TODO: Display the export resolution
                // const xResolution = Math.round(optimalExportParams.xResolution * 2 ** zoomOffset)
                // const yResolution = Math.round(optimalExportParams.yResolution * 2 ** zoomOffset)
                const isAvailable = minZoom <= zoom && zoom <= maxZoom

                radioInput.disabled = !isAvailable

                if (radioInput.checked && !isAvailable) {
                    radioInput.checked = false
                    radioInput.dispatchEvent(new Event("change"))
                }
            }
        }

        // On marker checkbox change, display/hide the marker
        const onMarkerCheckboxChange = () => {
            if (markerCheckbox.checked) {
                if (!marker) {
                    marker = L.marker(map.getCenter(), { draggable: true })
                    marker.on("dragend", onMarkerDragEnd)
                } else {
                    marker.setLatLng(map.getCenter())
                }

                // Display marker and chance zoom mode to center
                map.addLayer(marker)
                map.options.scrollWheelZoom = map.options.doubleClickZoom = "center"
            } else {
                // Hide marker and reset zoom mode
                map.removeLayer(marker)
                map.options.scrollWheelZoom = map.options.doubleClickZoom = true
            }
        }

        const onExportFormSubmit = (e) => {
            e.preventDefault()

            const format = exportFormatSelect.value
            const bounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
            const zoomOffset = parseInt(exportForm.querySelector(".detail-input:checked").value)
            const zoom = optimalExportParams.zoom + zoomOffset
            const baseLayer = getBaseLayer()

            // TODO: export call, disable button while exporting
        }

        // On custom region checkbox change, enable/disable the location filter
        const onCustomRegionCheckboxChange = () => {
            if (customRegionCheckbox.checked) {
                if (!locationFilter) {
                    locationFilter = getLocationFilter({
                        enableButton: false,
                        adjustButton: false,
                    })
                    locationFilter.addEventListener("change", onMapZoomOrLayerChange)
                }

                // By default, location filter is slightly smaller than the current view
                locationFilter.setBounds(map.getBounds().pad(-0.2))

                map.addLayer(locationFilter)
            } else {
                map.removeLayer(locationFilter)
            }

            onMapZoomOrLayerChange()
        }

        // On marker drag end, center map to marker
        const onMarkerDragEnd = () => {
            map.removeEventListener("move", onMapMove)
            map.panTo(marker.getLatLng())
            map.addOneTimeEventListener("moveend", () => {
                map.addEventListener("move", onMapMove)
            })
        }

        const inputOnChange = () => {
            // On sidebar shown, force update
            if (input.checked) {
                onMapMoveEnd()
                onMapZoomOrLayerChange()
            } else {
                // On sidebar hidden, deselect the marker checkbox
                // biome-ignore lint/style/useCollapsedElseIf: Readability
                if (markerCheckbox.checked) {
                    markerCheckbox.checked = false
                    markerCheckbox.dispatchEvent(new Event("change"))
                }
            }
        }

        // Listen for events
        map.addEventListener("move", onMapMove)
        map.addEventListener("moveend", onMapMoveEnd)
        map.addEventListener("zoomend baselayerchange", onMapZoomOrLayerChange)
        input.addEventListener("change", inputOnChange)
        markerCheckbox.addEventListener("change", onMarkerCheckboxChange)
        linkRadioInput.addEventListener("change", () => {
            if (linkRadioInput.checked) updateLinks()
        })
        shortLinkRadioInput.addEventListener("change", () => {
            if (shortLinkRadioInput.checked) updateLinks()
        })
        embedRadioInput.addEventListener("change", () => {
            if (embedRadioInput.checked) updateLinks()
        })
        exportForm.addEventListener("submit", onExportFormSubmit)
        customRegionCheckbox.addEventListener("change", onCustomRegionCheckboxChange)

        return container
    }

    return control
}
