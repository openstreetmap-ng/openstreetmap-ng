import type { Map as MaplibreMap } from "maplibre-gl"
import { config } from "../_config"
import { setPageTitle } from "../_title"
import { throttle, zoomPrecision } from "../_utils"
import { LocationFilterControl } from "../leaflet/_location-filter.ts"
import { padLngLatBounds } from "../leaflet/_utils.ts"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

/** Create a new export controller */
export const getExportController = (map: MaplibreMap): IndexController => {
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
    let locationFilter: LocationFilterControl | null = null

    // On custom region checkbox change, enable/disable the location filter
    customRegionCheckbox.addEventListener("change", () => {
        console.debug("onCustomRegionCheckboxChange", customRegionCheckbox.checked)
        if (customRegionCheckbox.checked) {
            if (!locationFilter) {
                locationFilter = new LocationFilterControl()
                locationFilter.addOnRenderHandler(throttle(() => updateState(), 250))
            }
            // By default, location filter is slightly smaller than the current view
            locationFilter.addTo(map, padLngLatBounds(map.getBounds(), -0.2))
        } else {
            locationFilter.remove()
        }
        updateState()
    })

    /** On map move end, update the inputs */
    const updateState = () => {
        const precision = zoomPrecision(map.getZoom())
        const bounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
        const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
        minLonInput.value = minLon.toFixed(precision)
        minLatInput.value = minLat.toFixed(precision)
        maxLonInput.value = maxLon.toFixed(precision)
        maxLatInput.value = maxLat.toFixed(precision)
        updateElements(minLon, minLat, maxLon, maxLat)
    }

    const updateElements = (minLon: number, minLat: number, maxLon: number, maxLat: number) => {
        // Update the form availability
        const currentViewAreaSize = (maxLon - minLon) * (maxLat - minLat)
        const isFormAvailable = currentViewAreaSize <= config.mapQueryAreaMaxSize
        exportAvailableContainer.classList.toggle("d-none", !isFormAvailable)
        exportUnavailableContainer.classList.toggle("d-none", isFormAvailable)

        // Update the export links
        const bboxQueryString = `?bbox=${minLon},${minLat},${maxLon},${maxLat}`
        exportLink.href = exportBaseHref + bboxQueryString
        exportOverpassLink.href = exportOverpassBaseHref + bboxQueryString
    }

    return {
        load: () => {
            switchActionSidebar(map, sidebar)
            setPageTitle(sidebarTitle)
            map.on("moveend", updateState)
            updateState()
        },
        unload: () => {
            map.off("moveend", updateState)
            // On sidebar hidden, deselect the custom region checkbox
            if (customRegionCheckbox.checked) {
                customRegionCheckbox.checked = false
                customRegionCheckbox.dispatchEvent(new Event("change"))
            }
        },
    }
}
