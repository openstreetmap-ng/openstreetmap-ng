import { encode } from "@googlemaps/polyline-codec"
import { Dropdown } from "bootstrap"
import * as L from "leaflet"
import { formatCoordinate } from "../_format-utils"
import { qsEncode } from "../_qs"
import { zoomPrecision } from "../_utils"
import { routerNavigateStrict } from "../index/_router"

export const newNoteMinZoom = 12
export const queryFeaturesMinZoom = 14

/**
 * Configure the map context menu
 */
export const configureContextMenu = (map: L.Map): void => {
    const mapContainer = map.getContainer()

    const containerTemplate = document.querySelector("template.context-menu-template") as HTMLTemplateElement
    const container = containerTemplate.content.firstElementChild as HTMLElement
    const dropdownButton = container.querySelector(".dropdown-toggle")
    const dropdown = Dropdown.getOrCreateInstance(dropdownButton)
    const geolocationField = container.querySelector(".geolocation-dd")
    const geolocationGeoField = container.querySelector(".geolocation-geo")
    const geolocationUriField = container.querySelector(".geolocation-uri")

    const routingFromButton: HTMLButtonElement = container.querySelector("button.routing-from")
    const routingToButton: HTMLButtonElement = container.querySelector("button.routing-to")
    const newNoteButton: HTMLButtonElement = container.querySelector("button.new-note")
    const showAddressButton: HTMLButtonElement = container.querySelector("button.show-address")
    const queryFeaturesButton: HTMLButtonElement = container.querySelector("button.query-features")
    const centerHereButton: HTMLButtonElement = container.querySelector("button.center-here")
    const measureDistanceButton: HTMLButtonElement = container.querySelector("button.measure-distance")

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

    const closePopup = () => {
        dropdown.hide()
        map.closePopup(popup)
    }

    // On map interactions, close the popup
    map.addEventListener("zoomstart movestart mouseout", closePopup)

    map.addEventListener("contextmenu", ({ latlng, containerPoint }: L.LeafletMouseEvent) => {
        // On map contextmenu, open the popup
        console.debug("onMapContextMenu", latlng)

        // Update the geolocation fields
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lon = latlng.lng.toFixed(precision)
        const lat = latlng.lat.toFixed(precision)
        geolocationField.textContent = `${lat}, ${lon}`
        geolocationGeoField.textContent = formatCoordinate(latlng.lat, latlng.lng)
        geolocationUriField.textContent = `geo:${lat},${lon}?z=${zoom}`

        // Open the context menu
        popup.setLatLng(latlng)
        map.openPopup(popup)

        // Ensure the popup is visible
        const element = popup.getElement()
        const popupSize = [element.clientWidth, element.clientHeight]
        const containerSize = [mapContainer.clientWidth, mapContainer.clientHeight]
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

    const onGeolocationFieldClick = async ({ target }: Event) => {
        // On geolocation field click, copy the text content
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

    routingFromButton.addEventListener("click", () => {
        // On routing from button click, navigate to routing page
        console.debug("onRoutingFromButtonClick")
        closePopup()
        const { lon, lat } = getPopupPosition()
        const from = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ from })}`)
    })

    routingToButton.addEventListener("click", () => {
        // On routing to button click, navigate to routing page
        console.debug("onRoutingToButtonClick")
        closePopup()
        const { lon, lat } = getPopupPosition()
        const to = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ to })}`)
    })

    newNoteButton.addEventListener("click", () => {
        // On new note button click, navigate to new-note page
        console.debug("onNewNoteButtonClick")
        closePopup()
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/note/new?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    })

    showAddressButton.addEventListener("click", () => {
        // On show address button click, navigate to search page
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

    queryFeaturesButton.addEventListener("click", () => {
        // On query features button click, navigate to query-features page
        console.debug("onQueryFeaturesButtonClick")
        closePopup()
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/query?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    })

    centerHereButton.addEventListener("click", () => {
        // On center here button click, center the map
        console.debug("onCenterHereButtonClick")
        closePopup()
        map.panTo(popup.getLatLng())
    })

    measureDistanceButton.addEventListener("click", () => {
        // On measure distance button click, open the distance tool
        console.debug("onMeasureDistanceButtonClick")
        closePopup()
        const { lon, lat } = getPopupPosition()
        const line = encode([[Number(lat), Number(lon)]], 5)
        routerNavigateStrict(`/distance?${qsEncode({ line })}`)
    })
}
