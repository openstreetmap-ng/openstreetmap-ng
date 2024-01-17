import * as L from "leaflet"
import "leaflet.locatecontrol"
import { isMetricUnit } from "../_utils.js"

// TODO: import (S)CSS?
// TODO: tooltip

export const getLocateControl = (options) => {
    const control = L.control.locate(
        Object.assign(
            {
                icon: "icon geolocate",
                iconLoading: "icon geolocate",
                metric: isMetricUnit,
                strings: {
                    title: I18n.t("javascripts.map.locate.title"),
                    popup: ({ distance, unit }) => {
                        return I18n.t(`javascripts.map.locate.${unit}Popup`, { count: distance })
                    },
                },
            },
            options,
        ),
    )

    return control
}
