import { routerNavigateStrict } from "@index/router"
import { zoomPrecision } from "@lib/coords"
import { formatCoordinate } from "@lib/format"
import { NEW_NOTE_MIN_ZOOM } from "@lib/map/controls/new-note"
import { QUERY_FEATURES_MIN_ZOOM } from "@lib/map/controls/query-features"
import { encodeMapState, getMapGeoUri, type LonLatZoom } from "@lib/map/state"
import { encodeLonLat } from "@lib/polyline"
import { qsEncode } from "@lib/qs"
import { Dropdown } from "bootstrap"
import { type Map as MaplibreMap, type MapMouseEvent, Popup } from "maplibre-gl"

export const configureContextMenu = (map: MaplibreMap) => {
  const mapContainer = map.getContainer()

  const containerTemplate = document.querySelector("template.context-menu-template")!
  const container = containerTemplate.content.firstElementChild as HTMLElement
  const dropdownButton = container.querySelector(".dropdown-toggle")!
  const dropdown = Dropdown.getOrCreateInstance(dropdownButton)
  const geolocationField = container.querySelector(".geolocation-dd")!
  const geolocationGeoField = container.querySelector(".geolocation-geo")!
  const geolocationUriField = container.querySelector(".geolocation-uri")!

  const routingFromButton = container.querySelector("button.routing-from")!
  const routingToButton = container.querySelector("button.routing-to")!
  const newNoteButton = container.querySelector("button.new-note")!
  const showAddressButton = container.querySelector("button.show-address-btn")!
  const queryFeaturesButton = container.querySelector("button.query-features")!
  const centerHereButton = container.querySelector("button.center-here")!
  const measureDistanceButton = container.querySelector("button.measure-distance")!

  const popup = new Popup({
    closeButton: false,
    closeOnMove: true,
    anchor: "top-left",
    className: "context-menu",
  }).setDOMContent(container)

  /**
   * Get the simplified position of the popup
   * @example
   * getPopupLonLatZoom()
   * // => { lon: 12.345678, lat: 23.456789, zoom: 17 }
   */
  const getPopupLonLatZoom = () => {
    const { lng, lat } = popup.getLngLat()
    return { lon: lng, lat, zoom: map.getZoom() } satisfies LonLatZoom
  }

  /** On map interactions, close the popup */
  const closePopup = () => {
    dropdown.hide()
    popup.remove()
  }

  // On map contextmenu, open the popup
  map.on("contextmenu", ({ point, lngLat }: MapMouseEvent) => {
    console.debug("ContextMenu: Opened", lngLat.lng, lngLat.lat)

    // Update the geolocation fields
    const zoom = map.getZoom()
    const state = {
      lon: lngLat.lng,
      lat: lngLat.lat,
      zoom,
    }

    const precision = zoomPrecision(zoom)
    geolocationField.textContent = `${state.lon.toFixed(precision)}, ${state.lat.toFixed(precision)}`
    geolocationGeoField.textContent = formatCoordinate(state)
    geolocationUriField.textContent = getMapGeoUri(state)

    // Open the context menu
    popup.setLngLat(lngLat).addTo(map)

    // Ensure the popup remains visible
    const element = popup.getElement()
    const isOverflowX = point.x + element.clientWidth + 30 >= mapContainer.clientWidth
    const isOverflowY = point.y + element.clientHeight + 30 >= mapContainer.clientHeight
    const translateX = isOverflowX ? "-100%" : "0%"
    const translateY = isOverflowY ? "-100%" : "0%"
    element.style.translate = `${translateX} ${translateY}`
  })

  // On map zoomend, update the available buttons
  map.on("zoomend", () => {
    const zoom = map.getZoom()
    newNoteButton.disabled = zoom < NEW_NOTE_MIN_ZOOM
    queryFeaturesButton.disabled = zoom < QUERY_FEATURES_MIN_ZOOM
  })

  /** On geolocation field click, copy the text content */
  const onGeolocationFieldClick = async ({ target }: Event) => {
    closePopup()
    try {
      const value = (target as Element).textContent
      await navigator.clipboard.writeText(value)
      console.debug("ContextMenu: Copied geolocation", value)
    } catch (error) {
      console.warn("ContextMenu: Failed to copy", error)
      alert(error.message)
    }
  }
  geolocationField.addEventListener("click", onGeolocationFieldClick)
  geolocationGeoField.addEventListener("click", onGeolocationFieldClick)
  geolocationUriField.addEventListener("click", onGeolocationFieldClick)

  // On routing from button click, navigate to routing page
  routingFromButton.addEventListener("click", () => {
    console.debug("ContextMenu: Route from clicked")
    const { lon, lat, zoom } = getPopupLonLatZoom()
    const precision = zoomPrecision(zoom)
    const from = `${lat.toFixed(precision)}, ${lon.toFixed(precision)}`
    closePopup()
    routerNavigateStrict(`/directions${qsEncode({ from })}`)
  })

  // On routing to button click, navigate to routing page
  routingToButton.addEventListener("click", () => {
    console.debug("ContextMenu: Route to clicked")
    const { lon, lat, zoom } = getPopupLonLatZoom()
    const precision = zoomPrecision(zoom)
    const to = `${lat.toFixed(precision)}, ${lon.toFixed(precision)}`
    closePopup()
    routerNavigateStrict(`/directions${qsEncode({ to })}`)
  })

  // On new note button click, navigate to new-note page
  newNoteButton.addEventListener("click", () => {
    console.debug("ContextMenu: New note clicked")
    const at = encodeMapState(getPopupLonLatZoom(), "")
    closePopup()
    routerNavigateStrict(`/note/new${qsEncode({ at })}`)
  })

  // On show address button click, navigate to search page
  showAddressButton.addEventListener("click", () => {
    console.debug("ContextMenu: Show address clicked")
    const at = encodeMapState(getPopupLonLatZoom(), "")
    closePopup()
    routerNavigateStrict(`/search${qsEncode({ at })}`)
  })

  // On query features button click, navigate to query-features page
  queryFeaturesButton.addEventListener("click", () => {
    console.debug("ContextMenu: Query features clicked")
    const at = encodeMapState(getPopupLonLatZoom(), "")
    closePopup()
    routerNavigateStrict(`/query${qsEncode({ at })}`)
  })

  // On center here button click, center the map
  centerHereButton.addEventListener("click", () => {
    console.debug("ContextMenu: Center here clicked")
    map.panTo(popup.getLngLat())
    closePopup()
  })

  // On measure distance button click, open the distance tool
  measureDistanceButton.addEventListener("click", () => {
    console.debug("ContextMenu: Measure distance clicked")
    const { lon, lat } = getPopupLonLatZoom()
    const line = encodeLonLat([[lon, lat]], 5)
    closePopup()
    routerNavigateStrict(`/distance${qsEncode({ line })}`)
  })
}
