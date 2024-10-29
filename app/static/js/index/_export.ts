import type * as L from "leaflet"
import { mapQueryAreaMaxSize } from "../_config"
import { getPageTitle } from "../_title"
import { zoomPrecision } from "../_utils"
import { getLocationFilter } from "../leaflet/_location-filter"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

/** Create a new export controller */
export const getExportController = (map: L.Map): IndexController => {
    const sidebar = getActionSidebar("export")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const minLonInput = sidebar.querySelector("input[name=min_lon]")
    const minLatInput = sidebar.querySelector("input[name=min_lat]")
    const maxLonInput = sidebar.querySelector("input[name=max_lon]")
    const maxLatInput = sidebar.querySelector("input[name=max_lat]")
    const customRegionCheckbox = sidebar.querySelector("input.custom-region-check")
    const exportAvailableContainer = sidebar.querySelector(".export-available-container")
    const exportLink = exportAvailableContainer.querySelector("a.export-link")
    const exportBaseHref = exportLink.href
    const exportUnavailableContainer = sidebar.querySelector(".export-unavailable-container")
    const exportOverpassLink = sidebar.querySelector("a.export-overpass-link")
    const exportOverpassBaseHref = exportOverpassLink.href

    // Null values until initialized
    let locationFilter: any | null = null

    // On custom region checkbox change, enable/disable the location filter
    customRegionCheckbox.addEventListener("change", () => {
        console.debug("onCustomRegionCheckboxChange", customRegionCheckbox.checked)
        if (customRegionCheckbox.checked) {
            if (!locationFilter) {
                locationFilter = getLocationFilter()
                locationFilter.addEventListener("change", onMapMoveEnd)
            }

            map.addLayer(locationFilter)

            // By default, location filter is slightly smaller than the current view
            locationFilter.setBounds(map.getBounds().pad(-0.2))
            locationFilter.enable()
        } else {
            map.removeLayer(locationFilter)
        }
        onMapMoveEnd()
    })

    /** On map move end, update the inputs */
    const onMapMoveEnd = () => {
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const bounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
        const minLon = bounds.getWest().toFixed(precision)
        const minLat = bounds.getSouth().toFixed(precision)
        const maxLon = bounds.getEast().toFixed(precision)
        const maxLat = bounds.getNorth().toFixed(precision)

        minLonInput.value = minLon
        minLatInput.value = minLat
        maxLonInput.value = maxLon
        maxLatInput.value = maxLat

        updateElements(minLon, minLat, maxLon, maxLat)
    }

    const updateElements = (minLon: number, minLat: number, maxLon: number, maxLat: number) => {
        // Update the from availability
        const currentViewAreaSize = (maxLon - minLon) * (maxLat - minLat)
        const isFormAvailable = currentViewAreaSize <= mapQueryAreaMaxSize
        exportAvailableContainer.classList.toggle("d-none", !isFormAvailable)
        exportUnavailableContainer.classList.toggle("d-none", isFormAvailable)

        // Update the export links
        const bboxQueryString = `?bbox=${minLon},${minLat},${maxLon},${maxLat}`
        exportLink.href = exportBaseHref + bboxQueryString
        exportOverpassLink.href = exportOverpassBaseHref + bboxQueryString
    }

    return {
        load: () => {
            switchActionSidebar(map, "export")
            document.title = getPageTitle(sidebarTitle)

            // Listen for events
            map.addEventListener("moveend", onMapMoveEnd)

            // Initial update to set the inputs
            onMapMoveEnd()
        },
        unload: () => {
            map.removeEventListener("moveend", onMapMoveEnd)

            // On sidebar hidden, deselect the custom region checkbox
            if (customRegionCheckbox.checked) {
                customRegionCheckbox.checked = false
                customRegionCheckbox.dispatchEvent(new Event("change"))
            }
        },
    }
}
