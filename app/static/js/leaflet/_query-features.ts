import { Tooltip } from "bootstrap"
import i18next from "i18next"
import type { IControl, Map as MaplibreMap } from "maplibre-gl"
import { emptyFeatureCollection, type LayerId, layersConfig } from "./_layers"

export const queryFeaturesMinZoom = 14

const layerId: LayerId = "query-features" as LayerId
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["circle"],
    layerOptions: {
        paint: {
            // TODO: https://maplibre.org/maplibre-style-spec/layers/#circle
        },
    },
})

export class QueryFeaturesControl implements IControl {
    public onAdd(map: MaplibreMap): HTMLElement {
        const container = document.createElement("div")
        container.className = "leaflet-control query-features"

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

        // TODO: active state, handle click on map, precision!

        /** On map zoom, change button availability */
        const updateState = () => {
            const zoom = map.getZoom()
            if (zoom < queryFeaturesMinZoom) {
                if (!button.disabled) {
                    button.blur()
                    button.disabled = true
                    Tooltip.getInstance(button).setContent({
                        ".tooltip-inner": i18next.t("javascripts.site.queryfeature_disabled_tooltip"),
                    })
                }
            } else if (button.disabled) {
                button.disabled = false
                Tooltip.getInstance(button).setContent({
                    ".tooltip-inner": i18next.t("javascripts.site.queryfeature_tooltip"),
                })
            }
        }

        // Listen for events
        map.on("zoomend", updateState)
        // Initial update to set button states
        updateState()
        return container
    }

    public onRemove(): void {
        // Not implemented
    }
}
