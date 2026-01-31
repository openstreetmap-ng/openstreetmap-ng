import { IndexRoute } from "@index/index"
import { NEW_NOTE_MIN_ZOOM, NewNoteRoute } from "@index/new-note"
import { routerNavigate, routerRoute } from "@index/router"
import { effect } from "@preact/signals"
import { Tooltip } from "bootstrap"
import { t } from "i18next"
import type { IControl, Map as MaplibreMap } from "maplibre-gl"

export class NewNoteControl implements IControl {
  public _container!: HTMLElement

  public onAdd(map: MaplibreMap) {
    const container = document.createElement("div")
    container.className = "maplibregl-ctrl maplibregl-ctrl-group new-note"

    // Create a button and a tooltip
    const buttonText = t("javascripts.site.createnote_tooltip")
    const button = document.createElement("button")
    button.type = "button"
    button.className = "control-btn"
    button.ariaLabel = buttonText
    const icon = document.createElement("img")
    icon.className = "icon new-note"
    icon.src = "/static/img/controls/_generated/new-note.webp"
    button.append(icon)
    container.append(button)

    const tooltip = new Tooltip(button, {
      title: buttonText,
      placement: "left",
    })

    // Effect: Update button active state
    effect(() => {
      button.classList.toggle("active", routerRoute.value === NewNoteRoute)
    })

    // On button click, navigate to the new note page
    button.addEventListener("click", () => {
      const isActive = routerRoute.value === NewNoteRoute
      routerNavigate(isActive ? IndexRoute : NewNoteRoute)
      button.blur()
    })

    /** On map zoom, change button availability */
    const updateState = () => {
      const shouldDisable = map.getZoom() < NEW_NOTE_MIN_ZOOM
      if (shouldDisable === button.disabled) return

      if (shouldDisable) {
        button.blur()
        button.disabled = true
        tooltip.setContent({
          ".tooltip-inner": t("javascripts.site.createnote_disabled_tooltip"),
        })
      } else {
        button.disabled = false
        tooltip.setContent({
          ".tooltip-inner": t("javascripts.site.createnote_tooltip"),
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
