import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"
import "leaflet.locatecontrol"
import { isMetricUnit } from "../_utils"

// TODO: onlocationerror

export const getGeolocateControl = () => {
    return L.control.locate({
        locateOptions: {
            timeout: 30_000, // 30 seconds
            maximumAge: 300_000, // 5 minutes
        },
        position: "topright",
        icon: "icon geolocate",
        iconLoading: "icon geolocate loading",
        metric: isMetricUnit,
        strings: {
            // @ts-ignore
            popup: ({ distance, unit }: { distance: number; unit: string }): string => {
                const count = Math.round(distance)
                // TODO: formatDistance(count)
                // hard-coded strings for searchability
                if (unit === "meters") return i18next.t("javascripts.map.locate.metersPopup", { count })
                if (unit === "feet") return i18next.t("javascripts.map.locate.feetPopup", { count })
                console.error("Unsupported geolocate unit", unit)
            },
        },
        createButtonCallback: (container, options) => {
            container.className = "leaflet-control geolocate"

            // Create button and tooltip
            const buttonText = i18next.t("javascripts.map.locate.title")
            const button = document.createElement("button")
            button.className = "control-button"
            button.ariaLabel = buttonText
            const icon = document.createElement("img")
            icon.className = options.icon
            icon.src = "/static/img/leaflet/_generated/geolocate.webp"
            button.appendChild(icon)
            container.appendChild(button)

            new Tooltip(button, {
                title: buttonText,
                placement: "left",
            })

            // @ts-ignore
            return { link: button as HTMLAnchorElement, icon }
        },
    })
}
