import * as L from "leaflet"
import { qsEncode } from "../_qs.js"
import { zoomPrecision } from "../_utils.js"
import { routerNavigateStrict } from "./_router.js"

const searchForm = document.querySelector(".search-form")

/**
 * Configure the search form
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const configureSearchForm = (map) => {
    const whereIsThisButton = searchForm.querySelector(".where-is-this")

    const onSubmit = (e) => {
        e.preventDefault()
        const query = searchForm.elements.q.value
        if (query) routerNavigateStrict(`/search?${qsEncode({ q: query })}`)
    }

    const onWhereIsThisClick = (e) => {
        e.preventDefault()
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const latLng = map.getCenter()
        routerNavigateStrict(
            `/search?${qsEncode({
                lat: latLng.lat.toFixed(precision),
                lon: latLng.lng.toFixed(precision),
                zoom: zoom,
            })}`,
        )
    }

    // Listen for events
    searchForm.addEventListener("submit", onSubmit)
    whereIsThisButton.addEventListener("click", onWhereIsThisClick)
}

/**
 * Set search to the given value
 * @returns {void}
 */
export const setSearchFormQuery = (value) => {
    if (searchForm) searchForm.elements.q.value = value
}
