import i18next from "i18next"
import * as L from "leaflet"
import { getLastSelectedExportFormat, setLastSelectedExportFormat } from "../_local-storage"
import { exportMapImage, getOptimalExportParams } from "./_image-export.js"
import { getLocationFilter } from "./_location-filter.js"
import { getMapBaseLayer, getMapEmbedHtml, getMapGeoUri, getMapShortUrl } from "./_map-utils.js"
import { getSidebarToggleButton } from "./_sidebar-toggle-button.js"
import { getMarkerIcon } from "./_utils.js"

export const getShareSidebarToggleButton = () => {
    const control = getSidebarToggleButton("share", "javascripts.share.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map) => {
        const container = controlOnAdd(map)
        const sidebar = control.sidebar
        const button = control.button

        const markerCheckbox = sidebar.querySelector(".marker-check")
        const linkInput = sidebar.querySelector(".link-input")
        const geoUriInput = sidebar.querySelector(".geo-uri-input")
        const embedInput = sidebar.querySelector(".embed-input")

        const exportForm = sidebar.querySelector(".export-form")
        const customRegionCheckbox = exportForm.querySelector(".custom-region-check")
        // TODO: disable unavailable zoom levels (on zoomend)
        const detailOffsetsWithElements = Array.from(exportForm.querySelectorAll("[name=detail]")).map((input) => [
            Number.parseInt(input.value),
            [input, input.closest("label").querySelector(".resolution")],
        ])
        const formatSelect = exportForm.querySelector(".format-select")
        const submitButton = exportForm.querySelector("[type=submit]")

        // Null values until initialized
        let marker = null
        let locationFilter = null
        let optimalExportParams = null

        const updateCopyInputs = () => {
            const showMarker = markerCheckbox.checked
            linkInput.value = getMapShortUrl(map, showMarker)
            geoUriInput.value = getMapGeoUri(map)
            embedInput.value = getMapEmbedHtml(map, showMarker ? marker.getLatLng() : null)
        }

        // On map move, update marker position if marker is enabled
        const onMapMove = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return
            if (markerCheckbox.checked) marker.setLatLng(map.getCenter())
        }

        // On map zoomend or moveend, update sidebar data
        const onMapZoomOrMoveEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            updateCopyInputs()
        }

        // On map zoomend or baselayerchange, update the optimal export params
        const onMapZoomOrLayerChange = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const baseLayer = getMapBaseLayer(map)

            // Get the current base layer's min and max zoom
            const minZoom = baseLayer.options.minZoom
            const maxZoom = baseLayer.options.maxNativeZoom ?? baseLayer.options.maxZoom

            const leafletBounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
            const sw = leafletBounds.getSouthWest()
            const ne = leafletBounds.getNorthEast()
            const bounds = [sw.lng, sw.lat, ne.lng, ne.lat]
            optimalExportParams = getOptimalExportParams(bounds)

            // Update the radio inputs availability
            for (const [zoomOffset, [input, resolutionSpan]] of detailOffsetsWithElements) {
                const zoom = optimalExportParams.zoom + zoomOffset
                const isAvailable = minZoom <= zoom && zoom <= maxZoom
                const isDisabled = !isAvailable

                // Skip updates if the input is already in the correct state
                if (input.disabled === isDisabled) continue

                // Don't show resolution for now: it's not compatible with SVG, PDF
                // const xResolution = Math.round(optimalExportParams.xResolution * 2 ** zoomOffset)
                // const yResolution = Math.round(optimalExportParams.yResolution * 2 ** zoomOffset)
                // resolutionSpan.textContent = `${xResolution}⨯${yResolution} px`

                input.disabled = isDisabled
                input.closest(".form-check").classList.toggle("disabled", isDisabled)

                if (input.checked && isDisabled) {
                    input.checked = false
                    input.dispatchEvent(new Event("change"))
                }
            }
        }

        // On marker drag end, center map to marker
        const onMarkerDragEnd = () => {
            map.removeEventListener("move", onMapMove)
            map.panTo(marker.getLatLng())
            map.addOneTimeEventListener("moveend", () => {
                map.addEventListener("move", onMapMove)
            })
        }

        // On marker checkbox change, display/hide the marker
        const onMarkerCheckboxChange = () => {
            if (markerCheckbox.checked) {
                if (!marker) {
                    marker = L.marker(map.getCenter(), {
                        icon: getMarkerIcon("blue", true),
                        draggable: true,
                        autoPan: true,
                    })
                    marker.addEventListener("dragend", onMarkerDragEnd)
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

        const onExportFormSubmit = async (e) => {
            e.preventDefault()

            if (submitButton.disabled) return

            const originalInner = submitButton.innerHTML
            submitButton.disabled = true
            submitButton.textContent = i18next.t("state.preparing")

            try {
                // Get export params from the form
                const mimeType = formatSelect.value
                const fileSuffix = formatSelect.selectedOptions[0].dataset.suffix
                const leafletBounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
                const sw = leafletBounds.getSouthWest()
                const ne = leafletBounds.getNorthEast()
                const bounds = [sw.lng, sw.lat, ne.lng, ne.lat]
                const zoomOffset = Number.parseInt(exportForm.querySelector("[name=detail]:checked").value)
                const zoom = optimalExportParams.zoom + zoomOffset
                const baseLayer = getMapBaseLayer(map)

                // Create image blob and download it
                const blob = await exportMapImage(mimeType, bounds, zoom, baseLayer)
                const url = URL.createObjectURL(blob)

                const now = new Date()
                const date = `${now.toISOString().slice(0, 10)} ${now.toLocaleTimeString().replace(/:/g, "-")}`

                const a = document.createElement("a")
                a.href = url
                a.download = `Map ${date}${fileSuffix}`
                a.click()

                URL.revokeObjectURL(url)
            } finally {
                submitButton.innerHTML = originalInner
                submitButton.disabled = false
            }
        }

        const onFormatSelectChange = (e) => {
            const format = e.target.value
            setLastSelectedExportFormat(format)
        }

        const restoreLastSelectedExportFormat = () => {
            const lastSelectedExportFormat = getLastSelectedExportFormat()
            if (lastSelectedExportFormat !== null) {
                // for loop instead of
                //   formatSelect.value = lastSelectedExportFormat
                // to avoid setting invalid value from local storage
                for (const option of formatSelect.options) {
                    if (option.value === lastSelectedExportFormat) {
                        option.selected = true
                        break
                    }
                }
            }
        }

        // On custom region checkbox change, enable/disable the location filter
        const onCustomRegionCheckboxChange = () => {
            if (customRegionCheckbox.checked) {
                if (!locationFilter) {
                    locationFilter = getLocationFilter()
                    locationFilter.addEventListener("change", onMapZoomOrLayerChange)
                }

                map.addLayer(locationFilter)

                // By default, location filter is slightly smaller than the current view
                locationFilter.setBounds(map.getBounds().pad(-0.2))
                locationFilter.enable()
            } else {
                map.removeLayer(locationFilter)
            }

            onMapZoomOrLayerChange()
        }

        const onSidebarButtonClick = () => {
            if (button.classList.contains("active")) {
                // On sidebar shown, force update
                onMapZoomOrMoveEnd()
                onMapZoomOrLayerChange()
            } else {
                // On sidebar hidden, deselect the marker checkbox
                if (markerCheckbox.checked) {
                    markerCheckbox.checked = false
                    markerCheckbox.dispatchEvent(new Event("change"))
                }

                // On sidebar hidden, deselect the custom region checkbox
                if (customRegionCheckbox.checked) {
                    customRegionCheckbox.checked = false
                    customRegionCheckbox.dispatchEvent(new Event("change"))
                }
            }
        }

        // Listen for events
        map.addEventListener("move", onMapMove)
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        map.addEventListener("zoomend baselayerchange", onMapZoomOrLayerChange)
        button.addEventListener("click", onSidebarButtonClick)
        markerCheckbox.addEventListener("change", onMarkerCheckboxChange)
        customRegionCheckbox.addEventListener("change", onCustomRegionCheckboxChange)
        // TODO: support svg/pdf fallback
        exportForm.addEventListener("submit", onExportFormSubmit)
        formatSelect.addEventListener("change", onFormatSelectChange)
        restoreLastSelectedExportFormat()

        return container
    }

    return control
}
