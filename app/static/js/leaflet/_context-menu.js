import * as L from "leaflet"
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
    const element = document.querySelector(".leaflet-context-menu")
    const routingFromButton = element.querySelector(".routing-from")
    const routingToButton = element.querySelector(".routing-to")
    const newNoteButton = element.querySelector(".new-note")
    const showAddressButton = element.querySelector(".show-address")
    const queryFeaturesButton = element.querySelector(".query-features")
    const centerHereButton = element.querySelector(".center-here")

    const popup = L.popup({
        closeButton: false,
        interactive: true,
        content: element,
        bubblingMouseEvents: false,
        popupAnchor: [0,0]
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
        popup.setLatLng(event.latlng)
        map.openPopup(popup)
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

    // Listen for events
    map.addEventListener("contextmenu", onMapContextMenu)
    map.addEventListener("zoomend", onMapZoomEnd)
    routingFromButton.addEventListener("click", onRoutingFromButtonClick)
    routingToButton.addEventListener("click", onRoutingToButtonClick)
    newNoteButton.addEventListener("click", onNewNoteButtonClick)
    showAddressButton.addEventListener("click", onShowAddressButtonClick)
    queryFeaturesButton.addEventListener("click", onQueryFeaturesButtonClick)
    centerHereButton.addEventListener("click", onCenterHereButtonClick)
}
