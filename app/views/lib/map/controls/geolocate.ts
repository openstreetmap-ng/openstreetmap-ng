import { MINUTE, SECOND } from "@std/datetime/constants"
import { Tooltip } from "bootstrap"
import { t } from "i18next"
import { GeolocateControl, type Map as MaplibreMap } from "maplibre-gl"

export class CustomGeolocateControl extends GeolocateControl {
    public constructor() {
        super({
            positionOptions: {
                maximumAge: 5 * MINUTE,
                timeout: 30 * SECOND,
            },
            trackUserLocation: true,
        })
    }

    public override onAdd(map: MaplibreMap) {
        const container = super.onAdd(map)
        const button = container.querySelector("button.maplibregl-ctrl-geolocate")!
        const buttonText = t("javascripts.map.locate.title")
        button.ariaLabel = buttonText
        new Tooltip(button, {
            title: buttonText,
            placement: "left",
        })
        const icon = document.createElement("img")
        icon.className = "icon geolocate"
        icon.src = "/static/img/controls/_generated/geolocate.webp"
        button.replaceChildren(icon)
        return container
    }
}
