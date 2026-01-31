import { IndexRoute } from "@index/index"
import { QUERY_FEATURES_MIN_ZOOM, QueryFeaturesRoute } from "@index/query-features"
import { routerNavigate, routerReplace, routerRoute } from "@index/router"
import { effect } from "@preact/signals"
import { Tooltip } from "bootstrap"
import { t } from "i18next"
import type { IControl, Map as MaplibreMap, MapMouseEvent } from "maplibre-gl"

export class QueryFeaturesControl implements IControl {
  public _container!: HTMLElement

  public onAdd(map: MaplibreMap) {
    const mapContainer = map.getContainer()
    const container = document.createElement("div")
    container.className = "maplibregl-ctrl maplibregl-ctrl-group query-features"

    // Create a button and a tooltip
    const buttonText = t("javascripts.site.queryfeature_tooltip")
    const button = document.createElement("button")
    button.type = "button"
    button.className = "control-btn"
    button.ariaLabel = buttonText
    const icon = document.createElement("img")
    icon.className = "icon query-features"
    icon.src = "/static/img/controls/_generated/query-features.webp"
    button.append(icon)
    container.append(button)

    const tooltip = new Tooltip(button, {
      title: buttonText,
      placement: "left",
    })

    const onMapClick = ({ lngLat }: MapMouseEvent) => {
      const zoom = Math.round(Math.max(map.getZoom(), QUERY_FEATURES_MIN_ZOOM))
      const at = { lon: lngLat.lng, lat: lngLat.lat, zoom }
      routerReplace(QueryFeaturesRoute, { at })
    }

    let active = false
    const setActive = (next: boolean) => {
      if (active === next) return
      active = next

      button.classList.toggle("active", active)
      mapContainer.classList.toggle("query-features", active)
      if (active) {
        map.on("click", onMapClick)
      } else {
        map.off("click", onMapClick)
      }
    }

    // Effect: Sync active state with the current route
    effect(() => {
      setActive(routerRoute.value === QueryFeaturesRoute)
    })

    // On button click, toggle the query-features sidebar.
    button.addEventListener("click", () => {
      const isActive = routerRoute.value === QueryFeaturesRoute
      routerNavigate(isActive ? IndexRoute : QueryFeaturesRoute)
      button.blur()
    })

    /** On map zoom, change button availability */
    const updateState = () => {
      const shouldDisable = map.getZoom() < QUERY_FEATURES_MIN_ZOOM
      if (shouldDisable === button.disabled) return

      if (shouldDisable) {
        button.disabled = true
        tooltip.setContent({
          ".tooltip-inner": t("javascripts.site.queryfeature_disabled_tooltip"),
        })
      } else {
        button.disabled = false
        tooltip.setContent({
          ".tooltip-inner": t("javascripts.site.queryfeature_tooltip"),
        })
      }
    }

    // Listen for events
    map.on("zoomend", updateState)
    // Initial update to set button states
    updateState()
    this._container = container
    return container
  }

  public onRemove() {
    // Not implemented
  }
}
