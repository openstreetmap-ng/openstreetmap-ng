import i18next from "i18next"
import * as L from "leaflet"
import { getLastShareExportFormat, setLastShareExportFormat } from "../_local-storage"
import type { Bounds } from "../_types"
import { exportMapImage, getOptimalExportParams } from "./_image-export"
import { getLocationFilter } from "./_location-filter"
import { getMapBaseLayer, getMapEmbedHtml, getMapGeoUri, getMapShortlink } from "./_map-utils"
import { getSidebarToggleButton } from "./_sidebar-toggle-button"
import { getMarkerIcon } from "./_utils"

export const getShareSidebarToggleButton = () => {
    const control = getSidebarToggleButton("share", "javascripts.share.title")
    const controlOnAdd = control.onAdd

    control.onAdd = (map: L.Map): HTMLElement => {
        const container = controlOnAdd(map)
        const button = container.querySelector("button")

        button.addEventListener("click", () => {
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
        })

        const sidebar = control.sidebar
        const linkInput = sidebar.querySelector("input.link-input")
        const geoUriInput = sidebar.querySelector("input.geo-uri-input")
        const embedInput = sidebar.querySelector("input.embed-input")

        let marker: L.Marker | null = null
        let locationFilter: any | null = null
        let optimalExportParams: { zoom: number; xResolution: number; yResolution: number } | null = null

        /** On marker drag end, center map on marker */
        const onMarkerDragEnd = () => {
            map.removeEventListener("move", onMapMove)
            map.panTo(marker.getLatLng())
            map.addOneTimeEventListener("moveend", () => {
                map.addEventListener("move", onMapMove)
            })
        }

        const markerCheckbox = sidebar.querySelector("input.marker-check")
        markerCheckbox.addEventListener("change", () => {
            // On marker checkbox change, display/hide the marker
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
        })

        const exportForm = sidebar.querySelector("form.export-form")
        const exportSubmitButton = exportForm.querySelector("button[type=submit]")

        // TODO: disable unavailable zoom levels (on zoomend)
        const detailOffsetsWithElements: [number, [HTMLInputElement, HTMLSpanElement]][] = []
        const detailInputs = exportForm.querySelectorAll("input[name=detail]")
        for (const input of detailInputs) {
            const zoomOffset = Number.parseInt(input.value, 10)
            const resolutionSpan = input.closest("label").querySelector("span.resolution")
            detailOffsetsWithElements.push([zoomOffset, [input, resolutionSpan]])
        }

        exportForm.addEventListener("submit", async (e) => {
            e.preventDefault()

            if (exportSubmitButton.disabled) return

            const originalInner = exportSubmitButton.innerHTML
            exportSubmitButton.disabled = true
            exportSubmitButton.textContent = i18next.t("state.preparing")

            try {
                // Get export params from the form
                const mimeType = formatSelect.value
                const fileSuffix = formatSelect.selectedOptions[0].dataset.suffix
                const leafletBounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
                const sw = leafletBounds.getSouthWest()
                const ne = leafletBounds.getNorthEast()
                const bounds: Bounds = [sw.lng, sw.lat, ne.lng, ne.lat] as const
                const selectedDetailInput = exportForm.querySelector("input[name=detail]:checked")
                const zoomOffset = Number.parseInt(selectedDetailInput.value, 10)
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
                exportSubmitButton.innerHTML = originalInner
                exportSubmitButton.disabled = false
            }
        })

        // On custom region checkbox change, enable/disable the location filter
        const customRegionCheckbox = exportForm.querySelector("input.custom-region-check")
        customRegionCheckbox.addEventListener("change", () => {
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
        })

        // TODO: support svg/pdf fallback
        const formatSelect = exportForm.querySelector("select.format-select")
        formatSelect.addEventListener("change", () => {
            const format = formatSelect.value
            console.debug("onFormatSelectChange", format)
            setLastShareExportFormat(format)
        })

        /** On map move, update marker position if marker is enabled */
        const onMapMove = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return
            if (markerCheckbox.checked) marker.setLatLng(map.getCenter())
        }
        map.addEventListener("move", onMapMove)

        /** On map zoomend or moveend, update sidebar data */
        const onMapZoomOrMoveEnd = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const showMarker = markerCheckbox.checked
            linkInput.value = getMapShortlink(map, showMarker)
            geoUriInput.value = getMapGeoUri(map)
            embedInput.value = getMapEmbedHtml(map, showMarker ? marker.getLatLng() : null)
        }
        map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)

        /** On map zoomend or baselayerchange, update the optimal export params */
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
            const bounds: Bounds = [sw.lng, sw.lat, ne.lng, ne.lat] as const
            optimalExportParams = getOptimalExportParams(bounds)

            // Update the radio inputs availability
            for (const [zoomOffset, [input, _]] of detailOffsetsWithElements) {
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
        map.addEventListener("zoomend baselayerchange", onMapZoomOrLayerChange)

        const lastShareExportFormat = getLastShareExportFormat()
        if (lastShareExportFormat) {
            // for loop instead of
            //   formatSelect.value = lastSelectedExportFormat
            // to avoid setting invalid value from local storage
            for (const option of formatSelect.options) {
                if (option.value === lastShareExportFormat) {
                    option.selected = true
                    break
                }
            }
        }

        return container
    }

    return control
}
