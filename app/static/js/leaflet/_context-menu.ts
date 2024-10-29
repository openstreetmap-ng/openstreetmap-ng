import { encode } from "@mapbox/polyline"
import { Dropdown } from "bootstrap"
import * as L from "leaflet"
import { formatCoordinate } from "../_format-utils"
import { qsEncode } from "../_qs"
import { zoomPrecision } from "../_utils"
import { routerNavigateStrict } from "../index/_router"

export const newNoteMinZoom = 12
export const queryFeaturesMinZoom = 14

/** Configure the map context menu */
export const configureContextMenu = (map: L.Map): void => {
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

    const popup = L.popup({
        content: container,
        className: "context-menu",
        autoPan: false,
        closeButton: false,
        // @ts-ignore
        bubblingMouseEvents: false,
    })

    /**
     * Get the simplified position of the popup
     * @example
     * getPopupPosition()
     * // => { lon: "12.345678", lat: "23.456789", zoom: 17 }
     */
    const getPopupPosition = (): { lon: string; lat: string; zoom: number } => {
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const { lat, lng } = popup.getLatLng()
        return {
            lon: lng.toFixed(precision),
            lat: lat.toFixed(precision),
            zoom,
        }
    }

    /** On map interactions, close the popup */
    const closePopup = () => {
        dropdown.hide()
        map.closePopup(popup)
    }
    map.addEventListener("zoomstart movestart mouseout", closePopup)

    // On map contextmenu, open the popup
    map.addEventListener("contextmenu", ({ latlng, containerPoint }: L.LeafletMouseEvent) => {
        console.debug("onMapContextMenu", latlng)

        // Update the geolocation fields
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lon = latlng.lng.toFixed(precision)
        const lat = latlng.lat.toFixed(precision)
        geolocationField.textContent = `${lat}, ${lon}`
        geolocationGeoField.textContent = formatCoordinate({ lon: latlng.lng, lat: latlng.lat })
        geolocationUriField.textContent = `geo:${lat},${lon}?z=${zoom}`

        // Open the context menu
        popup.setLatLng(latlng)
        map.openPopup(popup)

        // Ensure the popup is visible
        const element = popup.getElement()
        const popupSize = [element.clientWidth, element.clientHeight] as const
        const containerSize = [mapContainer.clientWidth, mapContainer.clientHeight] as const
        const isOverflowX = containerPoint.x + popupSize[0] + 30 >= containerSize[0]
        const isOverflowY = containerPoint.y + popupSize[1] + 30 >= containerSize[1]
        const translateX = isOverflowX ? "-100%" : "0%"
        const translateY = isOverflowY ? "-100%" : "0%"
        element.style.translate = `${translateX} ${translateY}`
    })

    map.addEventListener("zoomend", () => {
        // On map zoomend, update the available buttons
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
        closePopup()
        const { lon, lat } = getPopupPosition()
        const from = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ from })}`)
    })

    // On routing to button click, navigate to routing page
    routingToButton.addEventListener("click", () => {
        console.debug("onRoutingToButtonClick")
        closePopup()
        const { lon, lat } = getPopupPosition()
        const to = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ to })}`)
    })

    // On new note button click, navigate to new-note page
    newNoteButton.addEventListener("click", () => {
        console.debug("onNewNoteButtonClick")
        closePopup()
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/note/new?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    })

    // On show address button click, navigate to search page
    showAddressButton.addEventListener("click", () => {
        console.debug("onShowAddressButtonClick")
        closePopup()
        const { lon, lat } = getPopupPosition()
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
        closePopup()
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/query?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    })

    // On center here button click, center the map
    centerHereButton.addEventListener("click", () => {
        console.debug("onCenterHereButtonClick")
        closePopup()
        map.panTo(popup.getLatLng())
    })

    // On measure distance button click, open the distance tool
    measureDistanceButton.addEventListener("click", () => {
        console.debug("onMeasureDistanceButtonClick")
        closePopup()
        const { lon, lat } = getPopupPosition()
        const line = encode([[Number(lat), Number(lon)]], 5)
        routerNavigateStrict(`/distance?${qsEncode({ line })}`)
    })
}
