import { Tooltip } from "bootstrap"
import i18next from "i18next"
import { GlobeControl, type Map as MaplibreMap } from "maplibre-gl"

export class CustomGlobeControl extends GlobeControl {
    public override onAdd(map: MaplibreMap): HTMLElement {
        const container = super.onAdd(map)
        const button = container.querySelector("button.maplibregl-ctrl-globe")
        const buttonText = i18next.t("javascripts.map.globe.title")
        button.ariaLabel = buttonText
        new Tooltip(button, {
            title: buttonText,
            placement: "left",
        })
        const icon = document.createElement("img")
        icon.className = "icon globe"
        icon.src = "/static/img/leaflet/_generated/geolocate.webp" // TODO: Replace with proper icon
        button.replaceChildren(icon)
        return container
    }
}
