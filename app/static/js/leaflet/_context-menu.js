import * as L from "leaflet"
import { qsEncode } from "../_qs.js"
import { zoomPrecision } from "../_utils.js"
import { routerNavigateStrict } from "../index/_router.js"
import { formatLatLon } from "../_format-utils.js"

export const newNoteMinZoom = 12
export const queryFeaturesMinZoom = 14

/**
 * Configure the map context menu
 * @param {L.Map} map Leaflet map
 * @returns {void}
 */
export const configureContextMenu = (map) => {
    const element = document.querySelector(".context-menu")
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

    // remove element from DOM
    element.parentNode.removeChild(element)

    const popup = L.popup({
        content: element, // readd element to DOM
        closeButton: false,
        interactive: true,
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

        if (element.querySelector("button.show")) element.querySelector("button.show").click()

        const containerPoint = [event.containerPoint.x, event.containerPoint.y]
        const popupSize = [element.clientWidth, element.clientHeight]
        const containerSize = [map._container.clientWidth, map._container.clientHeight]

        const isOverflowX = containerPoint[0] + popupSize[0] + 30 >= containerSize[0]
        const isOverflowY = containerPoint[1] + popupSize[1] + 30 >= containerSize[1]

        const translateX = isOverflowX ? "-100%" : "0%"
        const translateY = isOverflowY ? "-100%" : "0%"

        popup._container.style.translate = `${translateX} ${translateY}`
    }

    // On map zoomend, update the available buttons
    const onMapZoomEnd = () => {
        const zoom = map.getZoom()
        newNoteButton.disabled = zoom < newNoteMinZoom
        queryFeaturesButton.disabled = zoom < queryFeaturesMinZoom
    }

    // On routing from button click, navigate to routing page
    const onRoutingFromButtonClick = () => {
        closePopup()
        const { lon, lat } = getPopupPosition()
        routerNavigateStrict(
            `/directions?${qsEncode({
                from: `${lat},${lon}`,
            })}`,
        )
    }

    // On routing to button click, navigate to routing page
    const onRoutingToButtonClick = () => {
        closePopup()
        const { lon, lat } = getPopupPosition()
        routerNavigateStrict(
            `/directions?${qsEncode({
                to: `${lat},${lon}`,
            })}`,
        )
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

    // On measure distance button click, measure distance
    const onMeasureDistanceButtonClick = () => {
        closePopup()
        const { lon, lat } = getPopupPosition()
        routerNavigateStrict(`/distance?${qsEncode({ pos: `${lat},${lon}` })}`)
    }

    const closePopup = () => {
        map.closePopup(popup)
    }

    const onGeolocationFieldClick = async (event) => {
        closePopup()
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
    // map.addEventListener("zoomstart movestart mouseout", closePopup)
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
