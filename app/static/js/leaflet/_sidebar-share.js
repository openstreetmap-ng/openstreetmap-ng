import i18next from "i18next"
import * as L from "leaflet"
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
        const copyGroups = sidebar.querySelectorAll(".copy-group")
        const linkInput = sidebar.querySelector(".link-input")
        const geoUriInput = sidebar.querySelector(".geo-uri-input")
        const embedInput = sidebar.querySelector(".embed-input")

        const exportForm = sidebar.querySelector(".export-form")
        const customRegionCheckbox = exportForm.querySelector(".custom-region-check")
        const offsetsWithDetailRadioInputs = Array.from(exportForm.querySelectorAll("[name=detail]")).map((input) => [
            parseInt(input.value),
            input,
        ])
        const formatSelect = exportForm.querySelector(".format-select")
        const exportButton = exportForm.querySelector("[type=submit]")

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

        // On copy group input focus, select all text
        const onCopyInputFocus = (e) => {
            e.target.select()
        }

        // On copy group button click, copy input and change tooltip text
        const onCopyButtonClick = async (e) => {
            const copyButton = e.target.closest("button")
            const copyIcon = copyButton.querySelector("i")
            const copyGroup = copyButton.closest(".copy-group")
            const copyInput = copyGroup.querySelector(".form-control")

            // Visual feedback
            copyInput.select()

            try {
                // Write to clipboard
                const text = copyInput.value
                await navigator.clipboard.writeText(text)
                console.debug("Copied to clipboard", text)
            } catch (error) {
                console.error("Failed to write to clipboard", error)
                alert(error.message)
                return
            }

            if (copyIcon.timeout) clearTimeout(copyIcon.timeout)

            copyIcon.classList.remove("bi-copy")
            copyIcon.classList.add("bi-check2")

            copyIcon.timeout = setTimeout(() => {
                copyIcon.classList.remove("bi-check2")
                copyIcon.classList.add("bi-copy")
            }, 1500)
        }

        const onExportFormSubmit = async (e) => {
            e.preventDefault()

            if (exportButton.disabled) return

            const originalInner = exportButton.innerHTML
            exportButton.disabled = true
            exportButton.textContent = i18next.t("javascripts.share.exporting")

            try {
                // Get export params from the form
                const mimeType = formatSelect.value
                const fileSuffix = formatSelect.selectedOptions[0].dataset.suffix
                const bounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
                const zoomOffset = parseInt(exportForm.querySelector(".detail-input:checked").value)
                const zoom = optimalExportParams.zoom + zoomOffset
                const baseLayer = getMapBaseLayer(map)

                // Create image blob and download it
                const blob = await exportMapImage(mimeType, bounds, zoom, baseLayer)

                const now = new Date()
                const date = `${now.toISOString().slice(0, 10)} ${now.toLocaleTimeString().replace(/:/g, "-")}`

                const a = document.createElement("a")
                a.href = URL.createObjectURL(blob)
                a.download = `Map ${date}${fileSuffix}`
                a.click()
            } finally {
                exportButton.innerHTML = originalInner
                exportButton.disabled = false
            }
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
        for (const copyGroup of copyGroups) {
            const copyInput = copyGroup.querySelector(".form-control")
            copyInput.addEventListener("focus", onCopyInputFocus)
            const copyButton = copyGroup.querySelector("button")
            copyButton.addEventListener("click", onCopyButtonClick)
        }
        customRegionCheckbox.addEventListener("change", onCustomRegionCheckboxChange)
        // TODO: support svg/pdf fallback
        // TODO: finish implementation
        exportForm.addEventListener("submit", onExportFormSubmit)

        return container
    }

    return control
}
