import i18next from "i18next"
import * as L from "leaflet"
import "leaflet.locatecontrol"
import { isMetricUnit } from "../_utils.js"

// TODO: import (S)CSS?
// TODO: tooltip

export const getGeolocateControl = (options) => {
    const control = L.control.locate(
        Object.assign(
            {
                icon: "icon geolocate",
                iconLoading: "icon geolocate",
                metric: isMetricUnit,
                strings: {
                    title: i18next.t("javascripts.map.locate.title"),
                    popup: ({ distance, unit }) => {
                        const count = Math.round(distance)
                        // hard-coded strings for searchability
                        if (unit === "meters") return i18next.t("javascripts.map.locate.metersPopup", { count })
                        if (unit === "feet") return i18next.t("javascripts.map.locate.feetPopup", { count })
                        console.error(`Unknown unit: ${unit}`)
                    },
                },
            },
            options,
        ),
    )

    return control
}
