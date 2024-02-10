import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"
import "leaflet.locatecontrol"
import { isMetricUnit } from "../_utils.js"

// TODO: onlocationerror

export const getGeolocateControl = () => {
    const control = L.control.locate({
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
                console.error(`Unknown unit: ${unit}`)
            },
        },
        createButtonCallback: (container, options) => {
            container.className = "leaflet-control geolocate"

            // Create button and tooltip
            const locateButton = document.createElement("button")
            locateButton.className = "control-button"
            locateButton.innerHTML = `<span class="${options.icon}"></span>`

            new Tooltip(locateButton, {
                title: i18next.t("javascripts.map.locate.title"),
                placement: "left",
            })

            // Add button to container
            container.appendChild(locateButton)

            return { link: locateButton, icon: locateButton.querySelector("span") }
        },
    })

    return control
}
