import { encode } from "@googlemaps/polyline-codec"
import { Dropdown } from "bootstrap"
import * as L from "leaflet"
import { formatCoordinate } from "../_format-utils.js"
import { qsEncode } from "../_qs.js"
import { zoomPrecision } from "../_utils.js"
import { routerNavigateStrict } from "../index/_router.js"

export const newNoteMinZoom = 12
export const queryFeaturesMinZoom = 14

/**
 * Configure the map context menu
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const configureContextMenu = (map) => {
    const mapContainer = map.getContainer()
    const container = document.querySelector("template.context-menu-template").content.firstElementChild
    const dropdownButton = container.querySelector(".dropdown-toggle")
    const dropdown = Dropdown.getOrCreateInstance(dropdownButton)
    const geolocationField = container.querySelector(".geolocation-dd")
    const geolocationGeoField = container.querySelector(".geolocation-geo")
    const geolocationUriField = container.querySelector(".geolocation-uri")
    const routingFromButton = container.querySelector(".routing-from")
    const routingToButton = container.querySelector(".routing-to")
    const newNoteButton = container.querySelector(".new-note")
    const showAddressButton = container.querySelector(".show-address")
    const queryFeaturesButton = container.querySelector(".query-features")
    const centerHereButton = container.querySelector(".center-here")
    const measureDistanceButton = container.querySelector(".measure-distance")

    const popup = L.popup({
        content: container,
        className: "context-menu",
        autoPan: false,
        closeButton: false,
        bubblingMouseEvents: false,
    })

    /**
     * Get the simplified position of the popup.
     * @returns {{lon: string, lat: string, zoom: number}}
     * @example
     * getPopupPosition()
     * // => { lon: "12.345678", lat: "23.456789", zoom: 17 }
     */
    const getPopupPosition = () => {
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

    // On map contextmenu, open the popup
    const onMapContextMenu = ({ latlng, containerPoint }) => {
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
    }

    // On map zoomend, update the available buttons
    const onMapZoomEnd = () => {
        const zoom = map.getZoom()
        newNoteButton.disabled = zoom < newNoteMinZoom
        queryFeaturesButton.disabled = zoom < queryFeaturesMinZoom
    }

    // On geolocation field click, copy the text
    const onGeolocationFieldClick = async ({ target }) => {
        closePopup()
        try {
            const value = target.textContent
            await navigator.clipboard.writeText(value)
            console.debug("Copied geolocation to clipboard", value)
        } catch (err) {
            console.error("Failed to copy geolocation", err)
        }
    }

    // On routing from button click, navigate to routing page
    const onRoutingFromButtonClick = () => {
        closePopup()
        const { lon, lat } = getPopupPosition()
        const from = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ from })}`)
    }

    // On routing to button click, navigate to routing page
    const onRoutingToButtonClick = () => {
        closePopup()
        const { lon, lat } = getPopupPosition()
        const to = `${lat}, ${lon}`
        routerNavigateStrict(`/directions?${qsEncode({ to })}`)
    }

    // On new note button click, navigate to new-note page
    const onNewNoteButtonClick = () => {
        closePopup()
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/note/new?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    }

    // On show address button click, navigate to search page
    const onShowAddressButtonClick = () => {
        closePopup()
        const { lon, lat } = getPopupPosition()
        routerNavigateStrict(
            `/search?${qsEncode({
                whereami: 1,
                query: `${lat},${lon}`,
            })}`,
        )
    }

    // On query features button click, navigate to query-features page
    const onQueryFeaturesButtonClick = () => {
        closePopup()
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/query?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    }

    // On center here button click, center the map
    const onCenterHereButtonClick = () => {
        closePopup()
        map.panTo(popup.getLatLng())
    }

    // On measure distance button click, open the distance tool
    const onDistanceButtonClick = () => {
        closePopup()
        const { lon, lat } = getPopupPosition()
        const line = encode([[lat, lon]], 5)
        routerNavigateStrict(`/distance?${qsEncode({ line })}`)
    }

    // Listen for events
    map.addEventListener("contextmenu", onMapContextMenu)
    map.addEventListener("zoomend", onMapZoomEnd)
    map.addEventListener("zoomstart movestart mouseout", closePopup)
    geolocationField.addEventListener("click", onGeolocationFieldClick)
    geolocationGeoField.addEventListener("click", onGeolocationFieldClick)
    geolocationUriField.addEventListener("click", onGeolocationFieldClick)
    routingFromButton.addEventListener("click", onRoutingFromButtonClick)
    routingToButton.addEventListener("click", onRoutingToButtonClick)
    newNoteButton.addEventListener("click", onNewNoteButtonClick)
    showAddressButton.addEventListener("click", onShowAddressButtonClick)
    queryFeaturesButton.addEventListener("click", onQueryFeaturesButtonClick)
    centerHereButton.addEventListener("click", onCenterHereButtonClick)
    measureDistanceButton.addEventListener("click", onDistanceButtonClick)
}
