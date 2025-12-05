import { SidebarToggleControl } from "@index/sidebar/_toggle-button"
import { isLatitude, isLongitude } from "@lib/coords"
import { shareExportFormatStorage } from "@lib/local-storage"
import { padLngLatBounds } from "@lib/map/bounds"
import { LocationFilterControl } from "@lib/map/controls/location-filter"
import { exportMapImage } from "@lib/map/export-image"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import {
    getInitialMapState,
    getMapEmbedHtml,
    getMapGeoUri,
    getMapShortlink,
} from "@lib/map/state"
import { qsParse } from "@lib/qs"
import i18next from "i18next"
import { type Map as MaplibreMap, Marker } from "maplibre-gl"

export class ShareSidebarToggleControl extends SidebarToggleControl {
    public _container: HTMLElement

    public constructor() {
        super("share", "javascripts.share.title")
    }

    public override onAdd(map: MaplibreMap) {
        const container = super.onAdd(map)
        const button = container.querySelector("button")

        button.addEventListener("click", () => {
            if (button.classList.contains("active")) {
                // On sidebar shown, force update
                updateSidebar()
            } else if (customRegionCheckbox.checked) {
                // On sidebar hidden, deselect the custom region checkbox
                customRegionCheckbox.checked = false
                customRegionCheckbox.dispatchEvent(new Event("change"))
            }
        })

        const exportForm = this.sidebar.querySelector("form.export-form")
        const exportSubmitButton = exportForm.querySelector("button[type=submit]")
        const attributionCheckbox = exportForm.querySelector("input.attribution-check")

        let marker: Marker | null = null
        const markerCheckbox = this.sidebar.querySelector("input.marker-check")
        markerCheckbox.addEventListener("change", () => {
            // On marker checkbox change, display/hide the marker
            if (markerCheckbox.checked) {
                if (!marker)
                    marker = new Marker({
                        anchor: MARKER_ICON_ANCHOR,
                        element: getMarkerIconElement("blue", true),
                        draggable: true,
                    })
                marker.setLngLat(map.getCenter()).addTo(map)
            } else {
                marker.remove()
            }
            updateSidebar()
        })

        // Initialize marker from URL search parameters
        const searchParams = qsParse(window.location.search)
        if (searchParams.mlon && searchParams.mlat) {
            const mlon = Number.parseFloat(searchParams.mlon)
            const mlat = Number.parseFloat(searchParams.mlat)
            if (isLongitude(mlon) && isLatitude(mlat)) {
                console.debug("Initializing marker from search params", [mlon, mlat])
                markerCheckbox.checked = true
                markerCheckbox.dispatchEvent(new Event("change"))
                marker.setLngLat([mlon, mlat])
            }
        } else if (searchParams.m !== undefined) {
            // Marker at the center
            const { lon, lat } = getInitialMapState(map)
            console.debug("Initializing marker at the center", [lon, lat])
            markerCheckbox.checked = true
            markerCheckbox.dispatchEvent(new Event("change"))
            marker.setLngLat([lon, lat])
        }

        // On custom region checkbox change, enable/disable the location filter
        let locationFilter: LocationFilterControl | null = null
        const customRegionCheckbox = exportForm.querySelector(
            "input.custom-region-check",
        )
        customRegionCheckbox.addEventListener("change", () => {
            if (customRegionCheckbox.checked) {
                locationFilter ??= new LocationFilterControl()
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
                const blob = await exportMapImage(
                    mimeType,
                    map,
                    customRegionCheckbox.checked ? locationFilter.getBounds() : null,
                    markerCheckbox.checked ? marker.getLngLat() : null,
                    attribution,
                )
                const url = URL.createObjectURL(blob)

                const now = new Date()
                const date = `${now.toISOString().slice(0, 10)} ${now.toLocaleTimeString().replaceAll(":", "-")}`

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
        formatSelect.addEventListener("change", () =>
            shareExportFormatStorage.set(formatSelect.value),
        )

        // Restore last form values
        const lastShareExportFormat = shareExportFormatStorage.get()
        const matchingOption = Array.from(formatSelect.options).find(
            (option) => option.value === lastShareExportFormat,
        )
        if (matchingOption) matchingOption.selected = true

        const linkInput = this.sidebar.querySelector("input.link-input")
        const geoUriInput = this.sidebar.querySelector("input.geo-uri-input")
        const embedInput = this.sidebar.querySelector("input.embed-input")
        const updateSidebar = () => {
            // Skip updates if the sidebar is hidden
            if (!button.classList.contains("active")) return

            const markerLngLat = markerCheckbox.checked ? marker.getLngLat() : null
            linkInput.value = getMapShortlink(map, markerLngLat)
            geoUriInput.value = getMapGeoUri(map)
            embedInput.value = getMapEmbedHtml(map, markerLngLat)
        }
        map.on("moveend", updateSidebar)

        this._container = container
        return container
    }
}
