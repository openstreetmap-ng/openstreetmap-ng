import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"
import "leaflet.locatecontrol"
import { isMetricUnit } from "../_utils.js"

// TODO: onlocationerror

export const getGeolocateControl = () => {
    const control = L.control.locate({
        locateOptions: {
            timeout: 30_000, // 30 seconds
            maximumAge: 300_000, // 5 minutes
        },
        position: "topright",
        icon: "icon geolocate",
        iconLoading: "icon geolocate loading",
        metric: isMetricUnit,
        strings: {
            popup: ({ distance, unit }) => {
                const count = Math.round(distance)
                // TODO: formatDistance(count)
                // hard-coded strings for searchability
                if (unit === "meters") return i18next.t("javascripts.map.locate.metersPopup", { count })
                if (unit === "feet") return i18next.t("javascripts.map.locate.feetPopup", { count })
                console.error("Unsupported unit", unit)
            },
        },
        createButtonCallback: (container, options) => {
            container.className = "leaflet-control geolocate"

            // Create button and tooltip
            const buttonText = i18next.t("javascripts.map.locate.title")
            const button = document.createElement("button")
            button.className = "control-button"
            button.ariaLabel = buttonText
            const iconContainer = document.createElement("div")
            iconContainer.className = options.icon
            const icon = document.createElement("img")
            icon.src = "/static/img/leaflet/geolocate.webp"
            iconContainer.appendChild(icon)
            button.appendChild(iconContainer)

            new Tooltip(button, {
                title: buttonText,
                placement: "left",
            })

            // Add button to container
            container.appendChild(button)

            return { link: button, icon: iconContainer }
        },
    })

    return control
}
