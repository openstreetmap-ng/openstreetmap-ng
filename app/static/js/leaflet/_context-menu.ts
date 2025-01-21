import { encode } from "@mapbox/polyline"
import { Dropdown } from "bootstrap"
import { type MapMouseEvent, type Map as MaplibreMap, Popup } from "maplibre-gl"
import { formatCoordinate } from "../_format-utils"
import { qsEncode } from "../_qs"
import { beautifyZoom, zoomPrecision } from "../_utils"
import { routerNavigateStrict } from "../index/_router"
import { newNoteMinZoom } from "./_new-note"
import { queryFeaturesMinZoom } from "./_query-features"

/** Configure the map context menu */
export const configureContextMenu = (map: MaplibreMap): void => {
    const mapContainer = map.getContainer()

    const containerTemplate = document.querySelector("template.context-menu-template")
    const container = containerTemplate.content.firstElementChild as HTMLElement
    const dropdownButton = container.querySelector(".dropdown-toggle")
    const dropdown = Dropdown.getOrCreateInstance(dropdownButton)
    const geolocationField = container.querySelector(".geolocation-dd")
    const geolocationGeoField = container.querySelector(".geolocation-geo")
    const geolocationUriField = container.querySelector(".geolocation-uri")

    const routingFromButton = container.querySelector("button.routing-from")
    const routingToButton = container.querySelector("button.routing-to")
    const newNoteButton = container.querySelector("button.new-note")
    const showAddressButton = container.querySelector("button.show-address")
    const queryFeaturesButton = container.querySelector("button.query-features")
    const centerHereButton = container.querySelector("button.center-here")
    const measureDistanceButton = container.querySelector("button.measure-distance")

    const popup = new Popup({
        closeButton: false,
        closeOnMove: true,
        anchor: "top-left",
        className: "context-menu",
    }).setDOMContent(container)

    /**
     * Get the simplified position of the popup
     * @example
     * getPopupPosition()
     * // => { lon: "12.345678", lat: "23.456789", zoom: 17 }
     */
    const getPopupPosition = (): { lon: string; lat: string; zoom: number } => {
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lngLat = popup.getLngLat()
        return {
            lon: lngLat.lng.toFixed(precision),
            lat: lngLat.lat.toFixed(precision),
            zoom,
        }
    }

    /** On map interactions, close the popup */
    const closePopup = () => {
        dropdown.hide()
        popup.remove()
    }

    // On map contextmenu, open the popup
    map.on("contextmenu", ({ point, lngLat }: MapMouseEvent) => {
        console.debug("onMapContextMenu", lngLat)

        // Update the geolocation fields
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lon = lngLat.lng.toFixed(precision)
        const lat = lngLat.lat.toFixed(precision)
        geolocationField.textContent = `${lat}, ${lon}`
        geolocationGeoField.textContent = formatCoordinate({ lon: lngLat.lng, lat: lngLat.lat })
        geolocationUriField.textContent = `geo:${lat},${lon}?z=${Math.floor(zoom)}`

        // Open the context menu
        popup.setLngLat(lngLat).addTo(map)

        // Ensure the popup remains visible
        const element = popup.getElement()
        const popupSize = [element.clientWidth, element.clientHeight] as const
        const containerSize = [mapContainer.clientWidth, mapContainer.clientHeight] as const
        const isOverflowX = point.x + popupSize[0] + 30 >= containerSize[0]
        const isOverflowY = point.y + popupSize[1] + 30 >= containerSize[1]
        const translateX = isOverflowX ? "-100%" : "0%"
        const translateY = isOverflowY ? "-100%" : "0%"
        element.style.translate = `${translateX} ${translateY}`
    })

    // On map zoomend, update the available buttons
    map.on("zoomend", () => {
        const zoom = map.getZoom()
        newNoteButton.disabled = zoom < newNoteMinZoom
        queryFeaturesButton.disabled = zoom < queryFeaturesMinZoom
    })

    /** On geolocation field click, copy the text content */
    const onGeolocationFieldClick = async ({ target }: Event) => {
        closePopup()
        try {
            const value = (target as Element).textContent
            await navigator.clipboard.writeText(value)
            console.debug("Copied geolocation to clipboard", value)
        } catch (err) {
            console.warn("Failed to copy geolocation", err)
        }
    }
    geolocationField.addEventListener("click", onGeolocationFieldClick)
    geolocationGeoField.addEventListener("click", onGeolocationFieldClick)
    geolocationUriField.addEventListener("click", onGeolocationFieldClick)

    // On routing from button click, navigate to routing page
    routingFromButton.addEventListener("click", () => {
        console.debug("onRoutingFromButtonClick")
        const { lon, lat } = getPopupPosition()
        closePopup()
        const from = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ from })}`)
    })

    // On routing to button click, navigate to routing page
    routingToButton.addEventListener("click", () => {
        console.debug("onRoutingToButtonClick")
        const { lon, lat } = getPopupPosition()
        closePopup()
        const to = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ to })}`)
    })

    // On new note button click, navigate to new-note page
    newNoteButton.addEventListener("click", () => {
        console.debug("onNewNoteButtonClick")
        const { lon, lat, zoom } = getPopupPosition()
        const zoomRounded = beautifyZoom(zoom)
        closePopup()
        routerNavigateStrict(`/note/new?lat=${lat}&lon=${lon}&zoom=${zoomRounded}`)
    })

    // On show address button click, navigate to search page
    showAddressButton.addEventListener("click", () => {
        console.debug("onShowAddressButtonClick")
        const { lon, lat } = getPopupPosition()
        closePopup()
        routerNavigateStrict(
            `/search?${qsEncode({
                whereami: "1",
                query: `${lat},${lon}`,
            })}`,
        )
    })

    // On query features button click, navigate to query-features page
    queryFeaturesButton.addEventListener("click", () => {
        console.debug("onQueryFeaturesButtonClick")
        const { lon, lat, zoom } = getPopupPosition()
        const zoomRounded = beautifyZoom(zoom)
        closePopup()
        routerNavigateStrict(`/query?lat=${lat}&lon=${lon}&zoom=${zoomRounded}`)
    })

    // On center here button click, center the map
    centerHereButton.addEventListener("click", () => {
        console.debug("onCenterHereButtonClick")
        map.panTo(popup.getLngLat())
        closePopup()
    })

    // On measure distance button click, open the distance tool
    measureDistanceButton.addEventListener("click", () => {
        console.debug("onMeasureDistanceButtonClick")
        const { lon, lat } = getPopupPosition()
        closePopup()
        const line = encode([[Number(lat), Number(lon)]], 5)
        routerNavigateStrict(`/distance?${qsEncode({ line })}`)
    })
}
