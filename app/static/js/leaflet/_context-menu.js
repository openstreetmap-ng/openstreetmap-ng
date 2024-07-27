import * as L from "leaflet"
import { qsEncode } from "../_qs.js"
import { zoomPrecision } from "../_utils.js"
import { routerNavigateStrict } from "../index/_router.js"

export const newNoteMinZoom = 12
export const queryFeaturesMinZoom = 14

/**
 * Format degrees to their correct math representation
 * @param {int} decimalDegree degrees
 * @returns {string}
 * @example formatDegrees(21.32123)
 * // => "21°19′16″"
 */
export const formatDegrees = (decimalDegree) => {
    const degrees = Math.floor(decimalDegree)
    const minutes = Math.floor((decimalDegree - degrees) * 60)
    const seconds = Math.round(((decimalDegree - degrees) * 60 - minutes) * 60)

    // Pad single digits with a leading zero
    const formattedDegrees = degrees < 10 ? `0${degrees}` : `${degrees}`
    const formattedSeconds = seconds < 10 ? `0${seconds}` : `${seconds}`
    const formattedMinutes = minutes < 10 ? `0${minutes}` : `${minutes}`

    return `${formattedDegrees}°${formattedMinutes}′${formattedSeconds}″`
}

/**
 * Format lat lon in cordinate system. See https://en.wikipedia.org/wiki/Geographic_coordinate_system
 * @param {L.LatLng} pos position on map
 * @returns {string}
 * @example formatLatLon({lat: 21.32123, 35.2134})
 * // => "21°19′16″N, 35°12′48″E"
 */

export const formatLatLon = (latLng) => {
    const lat = formatDegrees(latLng.lat)
    const lon = formatDegrees(latLng.lng)
    const lat_dir = latLng.lat == 0 ? "" : latLng.lat > 0 ? "N" : "S"
    const lon_dir = latLng.lat == 0 ? "" : latLng.lat > 0 ? "E" : "W"
    return `${lat}${lat_dir}, ${lon}${lon_dir}`
}

/**
 * Configure the map context menu
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const configureContextMenu = (map) => {
    const element = document.querySelector(".leaflet-context-menu")
    const geolocationField = element.querySelector(".geolocation-dd")
    const geolocationGeoField = element.querySelector(".geolocation-geo")
    const geolocationUriField = element.querySelector(".geolocation-uri")
    const routingFromButton = element.querySelector(".routing-from")
    const routingToButton = element.querySelector(".routing-to")
    const newNoteButton = element.querySelector(".new-note")
    const showAddressButton = element.querySelector(".show-address")
    const queryFeaturesButton = element.querySelector(".query-features")
    const centerHereButton = element.querySelector(".center-here")
    const measureDistanceButton = element.querySelector(".measure-distance")

    const popup = L.popup({
        closeButton: false,
        interactive: true,
        content: element,
        bubblingMouseEvents: false,
        autoPan: false,
    })

    const getPopupPosition = () => {
        const latLng = popup.getLatLng()
        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const lon = latLng.lng.toFixed(precision)
        const lat = latLng.lat.toFixed(precision)
        return { lon, lat, zoom }
    }

    // On map contextmenu, open the popup
    const onMapContextMenu = (event) => {
        const precision = zoomPrecision(map.getZoom())
        const lon = event.latlng.lng.toFixed(precision)
        const lat = event.latlng.lat.toFixed(precision)

        geolocationGeoField.innerText = formatLatLon(event.latlng)
        geolocationField.innerText = `${lat}, ${lon}`
        geolocationUriField.innerText = `geo:${lat},${lon}?z=${map.getZoom()}`
        popup.setLatLng(event.latlng)
        map.openPopup(popup)

        if (element.querySelector("button.show"))
            element.querySelector("button.show").click()
    }

    // On map zoomend, update the available buttons
    const onMapZoomEnd = () => {
        const zoom = map.getZoom()
        newNoteButton.disabled = zoom < newNoteMinZoom
        queryFeaturesButton.disabled = zoom < queryFeaturesMinZoom
    }

    // On routing from button click, navigate to routing page
    const onRoutingFromButtonClick = () => {
        map.closePopup(popup)
        const { lon, lat } = getPopupPosition()
        routerNavigateStrict(
            `/directions?${qsEncode({
                from: `${lat},${lon}`,
            })}`,
        )
    }

    // On routing to button click, navigate to routing page
    const onRoutingToButtonClick = () => {
        map.closePopup(popup)
        const { lon, lat } = getPopupPosition()
        routerNavigateStrict(
            `/directions?${qsEncode({
                to: `${lat},${lon}`,
            })}`,
        )
    }

    // On new note button click, navigate to new-note page
    const onNewNoteButtonClick = () => {
        map.closePopup(popup)
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/note/new?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    }

    // On show address button click, navigate to search page
    const onShowAddressButtonClick = () => {
        map.closePopup(popup)
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
        map.closePopup(popup)
        const { lon, lat, zoom } = getPopupPosition()
        routerNavigateStrict(`/query?lat=${lat}&lon=${lon}&zoom=${zoom}`)
    }

    // On center here button click, center the map
    const onCenterHereButtonClick = () => {
        map.closePopup(popup)
        map.panTo(popup.getLatLng())
    }

    // On measure distance button click, measure distance
    const onMeasureDistanceButtonClick = () => {
        map.closePopup(popup)
        const { lon, lat } = getPopupPosition()
        routerNavigateStrict(`/measure?${qsEncode({ pos: `${lat},${lon}` })}`)
    }

    const closePopup = () => {
        map.closePopup(popup)
    }

    const onGeolocationFieldClick = async (event) => {
        map.closePopup(popup)
        try {
            await navigator.clipboard.writeText(event.target.innerText)
            console.debug("Text copied to clipboard")
        } catch (err) {
            console.error("Failed to copy text: ", err)
        }
    }

    // Listen for events
    map.addEventListener("contextmenu", onMapContextMenu)
    map.addEventListener("zoomend", onMapZoomEnd)
    map.addEventListener("zoomstart movestart", closePopup)
    routingFromButton.addEventListener("click", onRoutingFromButtonClick)
    routingToButton.addEventListener("click", onRoutingToButtonClick)
    newNoteButton.addEventListener("click", onNewNoteButtonClick)
    showAddressButton.addEventListener("click", onShowAddressButtonClick)
    queryFeaturesButton.addEventListener("click", onQueryFeaturesButtonClick)
    centerHereButton.addEventListener("click", onCenterHereButtonClick)
    measureDistanceButton.addEventListener("click", onMeasureDistanceButtonClick)
    geolocationField.addEventListener("click", onGeolocationFieldClick)
    geolocationGeoField.addEventListener("click", onGeolocationFieldClick)
    geolocationUriField.addEventListener("click", onGeolocationFieldClick)
}
