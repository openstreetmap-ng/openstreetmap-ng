import { DistanceRoute } from "@index/distance"
import { NEW_NOTE_MIN_ZOOM, NewNoteRoute } from "@index/new-note"
import { QUERY_FEATURES_MIN_ZOOM, QueryFeaturesRoute } from "@index/query-features"
import { routerNavigate } from "@index/router"
import { ROUTING_QUERY_PRECISION, RoutingRoute } from "@index/routing"
import { SearchRoute } from "@index/search"
import { formatPoint, zoomPrecision } from "@lib/coords"
import { formatCoordinate } from "@lib/format"
import { getMapGeoUri, type LonLatZoom } from "@lib/map/state"
import { computed, signal } from "@preact/signals"
import { t } from "i18next"
import { LngLat, type Map as MaplibreMap, Point, Popup } from "maplibre-gl"
import type { TargetedMouseEvent } from "preact"
import { render } from "preact"

export const configureContextMenu = (map: MaplibreMap) => {
  const mapContainer = map.getContainer()

  const ctx = signal<LonLatZoom>({ lon: 0, lat: 0, zoom: 0 })

  const ctxCoordText = computed(() => {
    const { lon, lat, zoom } = ctx.value
    const precision = zoomPrecision(zoom)
    return `${lon.toFixed(precision)}, ${lat.toFixed(precision)}`
  })

  const ctxGeoText = computed(() => formatCoordinate(ctx.value))
  const ctxGeoUriText = computed(() => getMapGeoUri(ctx.value))

  const popupRoot = document.createElement("div")
  const popup = new Popup({
    closeButton: false,
    closeOnMove: true,
    anchor: "top-left",
    className: "context-menu",
  }).setDOMContent(popupRoot)

  const closePopup = () => {
    popup.remove()
  }

  const openPopupAt = (point: Point, lngLat: LngLat) => {
    ctx.value = { lon: lngLat.lng, lat: lngLat.lat, zoom: map.getZoom() }

    popup.setLngLat(lngLat).addTo(map)

    requestAnimationFrame(() => {
      const element = popup.getElement()
      const isOverflowX = point.x + element.clientWidth + 30 >= mapContainer.clientWidth
      const isOverflowY =
        point.y + element.clientHeight + 30 >= mapContainer.clientHeight
      const translateX = isOverflowX ? "-100%" : "0%"
      const translateY = isOverflowY ? "-100%" : "0%"
      element.style.translate = `${translateX} ${translateY}`
    })
  }

  const ContextMenu = () => {
    const onCopy = async ({ currentTarget }: TargetedMouseEvent<HTMLButtonElement>) => {
      closePopup()
      const value = currentTarget.textContent.trim()
      try {
        await navigator.clipboard.writeText(value)
        console.debug("ContextMenu: Copied geolocation", value)
      } catch (error) {
        console.warn("ContextMenu: Failed to copy", error)
        alert(error.message)
      }
    }

    return (
      <nav role="menu">
        <div class="d-flex">
          <button
            type="button"
            class="btn flex-grow-1"
            onClick={onCopy}
          >
            {ctxCoordText.value}
          </button>
          <button
            type="button"
            class="btn dropdown-toggle dropdown-toggle-split"
            data-bs-toggle="dropdown"
            aria-expanded="false"
          />
          <ul class="dropdown-menu">
            <li>
              <button
                type="button"
                class="btn dropdown-item"
                onClick={onCopy}
              >
                {ctxGeoText.value}
              </button>
            </li>
            <li>
              <button
                type="button"
                class="btn dropdown-item"
                onClick={onCopy}
              >
                {ctxGeoUriText.value}
              </button>
            </li>
          </ul>
        </div>

        <button
          type="button"
          class="btn"
          onClick={() => {
            const from = formatPoint(ctx.value, ROUTING_QUERY_PRECISION)
            closePopup()
            routerNavigate(RoutingRoute, { from })
          }}
        >
          {t("javascripts.context.directions_from")}
        </button>
        <button
          type="button"
          class="btn"
          onClick={() => {
            const to = formatPoint(ctx.value, ROUTING_QUERY_PRECISION)
            closePopup()
            routerNavigate(RoutingRoute, { to })
          }}
        >
          {t("javascripts.context.directions_to")}
        </button>
        <button
          type="button"
          class="btn"
          disabled={ctx.value.zoom < NEW_NOTE_MIN_ZOOM}
          onClick={() => {
            closePopup()
            routerNavigate(NewNoteRoute, { at: ctx.value })
          }}
        >
          {t("context_menu.suggest_edit")}
        </button>
        <button
          type="button"
          class="btn"
          onClick={() => {
            closePopup()
            routerNavigate(SearchRoute, { at: ctx.value })
          }}
        >
          {t("javascripts.context.show_address")}
        </button>
        <button
          type="button"
          class="btn"
          disabled={ctx.value.zoom < QUERY_FEATURES_MIN_ZOOM}
          onClick={() => {
            closePopup()
            routerNavigate(QueryFeaturesRoute, { at: ctx.value })
          }}
        >
          {t("javascripts.context.query_features")}
        </button>
        <button
          type="button"
          class="btn"
          onClick={() => {
            closePopup()
            map.panTo(ctx.value)
          }}
        >
          {t("javascripts.context.centre_map")}
        </button>
        <button
          type="button"
          class="btn"
          onClick={() => {
            const { lon, lat } = ctx.value
            const line = [[lon, lat]] as const
            closePopup()
            routerNavigate(DistanceRoute, { line })
          }}
        >
          {t("context_menu.measure_distance")}
        </button>
      </nav>
    )
  }

  render(<ContextMenu />, popupRoot)

  map.on("contextmenu", ({ point, lngLat }) => {
    console.debug("ContextMenu: Opened", lngLat.lng, lngLat.lat)
    openPopupAt(point, lngLat)
  })
}
