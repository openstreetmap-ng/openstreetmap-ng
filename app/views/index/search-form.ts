import { routerNavigateStrict } from "@index/router"
import { beautifyZoom, zoomPrecision } from "@lib/coords"
import { qsEncode } from "@lib/qs"
import type { Map as MaplibreMap } from "maplibre-gl"

const searchForm = document.querySelector("form.search-form")
const searchQueryInput = searchForm?.querySelector("input[name=q]")

/** Configure the search form */
export const configureSearchForm = (map: MaplibreMap): void => {
    // On search form submit, capture and perform router navigation
    searchForm.addEventListener("submit", (e) => {
        console.debug("onSearchFormSubmit")
        e.preventDefault()
        const query = searchQueryInput.value
        if (query) routerNavigateStrict(`/search?${qsEncode({ q: query })}`)
    })

    const whereIsThisButton = searchForm.querySelector("button.where-is-this")
    whereIsThisButton.addEventListener("click", () => {
        console.debug("onWhereIsThisButtonClick")
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lngLat = map.getCenter()
        routerNavigateStrict(
            `/search?${qsEncode({
                lat: lngLat.lat.toFixed(precision),
                lon: lngLat.lng.toFixed(precision),
                zoom: beautifyZoom(zoom),
            })}`,
        )
    })
}

/** Set search form to the given query */
export const setSearchFormQuery = (query: string): void => {
    if (!searchForm) {
        console.error("Attempted to set search query but search form is not available")
        return
    }
    searchQueryInput.value = query
}
