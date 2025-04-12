import { Tooltip } from "bootstrap"
import i18next from "i18next"
import type { IControl, MapMouseEvent, Map as MaplibreMap } from "maplibre-gl"
import { beautifyZoom } from "../utils"
import { routerNavigateStrict } from "../../index/_router"

export const queryFeaturesMinZoom = 14

export class QueryFeaturesControl implements IControl {
    public _container: HTMLElement

    public onAdd(map: MaplibreMap): HTMLElement {
        const mapContainer = map.getContainer()
        const container = document.createElement("div")
        container.className = "maplibregl-ctrl maplibregl-ctrl-group query-features"

        // Create a button and a tooltip
        const buttonText = i18next.t("javascripts.site.queryfeature_tooltip")
        const button = document.createElement("button")
        button.type = "button"
        button.className = "control-button"
        button.ariaLabel = buttonText
        const icon = document.createElement("img")
        icon.className = "icon query-features"
        icon.src = "/static/img/leaflet/_generated/query-features.webp"
        button.appendChild(icon)
        container.appendChild(button)

        new Tooltip(button, {
            title: buttonText,
            placement: "left",
        })

        const onMapClick = ({ lngLat }: MapMouseEvent): void => {
            const zoom = map.getZoom()
            const zoomRounded = beautifyZoom(zoom)
            routerNavigateStrict(
                `/query?lat=${lngLat.lat}&lon=${lngLat.lng}&zoom=${zoomRounded}`,
            )
        }

        // On button click, toggle active state and event handlers
        button.addEventListener("click", () => {
            button.blur()
            const isActive = button.classList.toggle("active")
            if (isActive) {
                mapContainer.classList.add("query-features")
                map.on("click", onMapClick)
            } else {
                mapContainer.classList.remove("query-features")
                map.off("click", onMapClick)
            }
        })

        /** On map zoom, change button availability */
        const updateState = () => {
            const zoom = map.getZoom()
            if (zoom < queryFeaturesMinZoom) {
                if (!button.disabled) {
                    if (button.classList.contains("active")) button.click()
                    button.blur()
                    button.disabled = true
                    Tooltip.getInstance(button).setContent({
                        ".tooltip-inner": i18next.t(
                            "javascripts.site.queryfeature_disabled_tooltip",
                        ),
                    })
                }
            } else if (button.disabled) {
                button.disabled = false
                Tooltip.getInstance(button).setContent({
                    ".tooltip-inner": i18next.t(
                        "javascripts.site.queryfeature_tooltip",
                    ),
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

    public onRemove(): void {
        // Not implemented
    }
}
