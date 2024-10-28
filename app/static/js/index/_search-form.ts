import type * as L from "leaflet"
import { qsEncode } from "../_qs"
import { zoomPrecision } from "../_utils"
import { routerNavigateStrict } from "./_router"

const searchForm: HTMLFormElement | null = document.querySelector("form.search-form")
const searchQueryInput: HTMLInputElement | null = searchForm
    ? (searchForm.elements.namedItem("q") as HTMLInputElement)
    : null

/** Configure the search form */
export const configureSearchForm = (map: L.Map): void => {
    searchForm.addEventListener("submit", (e) => {
        // On search form submit, capture and perform router navigation
        e.preventDefault()
        const query = searchQueryInput.value
        if (query) routerNavigateStrict(`/search?${qsEncode({ q: query })}`)
    })

    const whereIsThisButton: HTMLButtonElement = searchForm.querySelector("button.where-is-this")
    whereIsThisButton.addEventListener("click", (e) => {
        e.preventDefault()
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const latLng = map.getCenter()
        routerNavigateStrict(
            `/search?${qsEncode({
                lat: latLng.lat.toFixed(precision),
                lon: latLng.lng.toFixed(precision),
                zoom: zoom.toString(),
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
