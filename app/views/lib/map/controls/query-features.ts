import { routerNavigateStrict } from "@index/router"
import { encodeMapState } from "@lib/map/state"
import { Tooltip } from "bootstrap"
import { t } from "i18next"
import type { IControl, Map as MaplibreMap, MapMouseEvent } from "maplibre-gl"

export const QUERY_FEATURES_MIN_ZOOM = 14

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
    button.appendChild(icon)
    container.appendChild(button)

    const tooltip = new Tooltip(button, {
      title: buttonText,
      placement: "left",
    })

    const onMapClick = ({ lngLat }: MapMouseEvent) => {
      const zoom = Math.max(map.getZoom(), QUERY_FEATURES_MIN_ZOOM)
      const at = encodeMapState({ lon: lngLat.lng, lat: lngLat.lat, zoom }, "?at=")
      routerNavigateStrict(`/query${at}`)
    }

    let active = false
    const setActive = (next: boolean) => {
      if (active === next) return
      active = next

      button.blur()
      button.classList.toggle("active", active)
      mapContainer.classList.toggle("query-features", active)
      if (active) {
        map.on("click", onMapClick)
      } else {
        map.off("click", onMapClick)
      }
    }

    button.addEventListener("click", () => {
      if (button.disabled) return
      setActive(!active)
    })

    /** On map zoom, change button availability */
    const updateState = () => {
      const shouldDisable = map.getZoom() < QUERY_FEATURES_MIN_ZOOM
      if (shouldDisable === button.disabled) return

      if (shouldDisable) {
        setActive(false)
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
