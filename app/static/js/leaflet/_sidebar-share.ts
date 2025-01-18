import i18next from "i18next"
import { type Map as MaplibreMap, Marker } from "maplibre-gl"
import { getLastShareExportFormat, setLastShareExportFormat } from "../_local-storage"
import { exportMapImage } from "./_image-export"
import { LocationFilterControl } from "./_location-filter"
import { getMapEmbedHtml, getMapGeoUri, getMapShortlink } from "./_map-utils"
import { SidebarToggleControl } from "./_sidebar-toggle-button"
import { getMarkerIconElement, markerIconAnchor, padLngLatBounds } from "./_utils.ts"

export class ShareSidebarToggleControl extends SidebarToggleControl {
    constructor() {
        super("share", "javascripts.share.title")
    }

    public onAdd(map: MaplibreMap): HTMLElement {
        const container = super.onAdd(map)
        const button = container.querySelector("button")

        button.addEventListener("click", () => {
            if (button.classList.contains("active")) {
                // On sidebar shown, force update
                updateSidebar()
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

        const exportForm = this.sidebar.querySelector("form.export-form")
        const exportSubmitButton = exportForm.querySelector("button[type=submit]")
        const attributionCheckbox = exportForm.elements.namedItem("attribution") as HTMLInputElement

        let marker: Marker | null = null
        const markerCheckbox = this.sidebar.querySelector("input.marker-check")
        markerCheckbox.addEventListener("change", () => {
            // On marker checkbox change, display/hide the marker
            if (markerCheckbox.checked) {
                if (!marker) {
                    marker = new Marker({
                        anchor: markerIconAnchor,
                        element: getMarkerIconElement("blue", true),
                        draggable: true,
                    })
                }
                marker.setLngLat(map.getCenter())
                marker.addTo(map)
            } else {
                marker.remove()
            }
        })

        // On custom region checkbox change, enable/disable the location filter
        let locationFilter: LocationFilterControl | null = null
        const customRegionCheckbox = exportForm.querySelector("input.custom-region-check")
        customRegionCheckbox.addEventListener("change", () => {
            if (customRegionCheckbox.checked) {
                if (!locationFilter) {
                    locationFilter = new LocationFilterControl()
                }
                // By default, location filter is slightly smaller than the current view
                locationFilter.addTo(map, padLngLatBounds(map.getBounds(), -0.2))
            } else {
                locationFilter.remove()
            }
        })

        exportForm.addEventListener("submit", async (e) => {
            e.preventDefault()

            if (exportSubmitButton.disabled) return

            const originalInner = exportSubmitButton.innerHTML
            exportSubmitButton.disabled = true
            exportSubmitButton.textContent = i18next.t("state.preparing")

            try {
                // Get export params from the form
                const attribution = attributionCheckbox.checked
                const mimeType = formatSelect.value
                const fileSuffix = formatSelect.selectedOptions[0].dataset.suffix

                // Create image blob and download it
                const blob = await exportMapImage(mimeType, map, locationFilter?.getBounds(), attribution)
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

        // On format change, remember the selection
        const formatSelect = exportForm.querySelector("select.format-select")
        formatSelect.addEventListener("change", () => {
            const format = formatSelect.value
            console.debug("onFormatSelectChange", format)
            setLastShareExportFormat(format)
        })

        // Restore last form values
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

        const linkInput = this.sidebar.querySelector("input.link-input")
        const geoUriInput = this.sidebar.querySelector("input.geo-uri-input")
        const embedInput = this.sidebar.querySelector("input.embed-input")
        const updateSidebar = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const showMarker = markerCheckbox.checked
            linkInput.value = getMapShortlink(map, showMarker)
            geoUriInput.value = getMapGeoUri(map)
            embedInput.value = getMapEmbedHtml(map, showMarker ? marker.getLngLat() : null)
        }
        map.on("moveend", updateSidebar)

        return container
    }
}
