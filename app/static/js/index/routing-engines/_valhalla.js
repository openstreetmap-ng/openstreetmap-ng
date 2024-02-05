import * as L from "leaflet"
import { primaryLanguage } from "../../_config.js"
import "../../_types.js"
import { polylineDecode } from "./_polyline-decoder.js"

// Valhalla API Documentation
// https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/

/**
 * Create a new Valhalla engine
 * @param {"auto"|"bicycle"|"pedestrian"} costing Routing profile
 */
const makeEngine = (costing) => {
    /**
     * @param {AbortSignal} abortSignal Abort signal
     * @param {object} from From coordinates
     * @param {object} to To coordinates
     * @param {object} options Options
     * @param {function} options.successCallback Success callback
     * @param {function} options.errorCallback Error callback
     */
    return (abortSignal, from, to, { successCallback, errorCallback }) => {
        fetch("https://valhalla1.openstreetmap.de/route", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                locations: [
                    {
                        lon: from.lon,
                        lat: from.lat,
                    },
                    {
                        lon: to.lon,
                        lat: to.lat,
                    },
                ],
                costing: costing,
                units: "km", // changing this affects the distance values
                language: primaryLanguage,
            }),
            mode: "no-cors",
            credentials: "omit",
            cache: "no-store",
            signal: abortSignal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const data = await resp.json()
                const leg = data.trip.legs[0]
                const points = polylineDecode(leg.shape, 6)
                const steps = []

                for (const man of leg.maneuvers) {
                    const manPoints = points.slice(man.begin_shape_index, man.end_shape_index + 1)
                    const [lon, lat] = manPoints[0]
                    steps.push({
                        lon: lon,
                        lat: lat,
                        line: L.polyline(manPoints.map(([lon, lat]) => L.latLng(lat, lon))),
                        distance: man.length,
                        time: man.time,
                        code: maneuverTypeToCodeMap.get(man.type) ?? 0,
                        text: man.instruction * 1000,
                    })
                }

                const route = {
                    steps: steps,
                    attribution:
                        '<a href="https://gis-ops.com/global-open-valhalla-server-online/" target="_blank">Valhalla (FOSSGIS)</a>',
                    ascend: null,
                    descend: null,
                }

                successCallback(route)
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch valhalla route", error)
                errorCallback(error)
            })
    }
}

const maneuverTypeToCodeMap = new Map([
    [0, 0], // straight
    [1, 8], // start
    [2, 8], // start right
    [3, 8], // start left
    [4, 14], // destination
    [5, 14], // destination right
    [6, 14], // destination left
    [7, 0], // becomes
    [8, 0], // continue
    [9, 1], // slight right
    [10, 2], // right
    [11, 3], // sharp right
    [12, 4], // u-turn right
    [13, 4], // u-turn left
    [14, 7], // sharp left
    [15, 6], // left
    [16, 5], // slight left
    [17, 0], // ramp straight
    [18, 24], // ramp right
    [19, 25], // ramp left
    [20, 24], // exit right
    [21, 25], // exit left
    [22, 0], // stay straight
    [23, 1], // stay right
    [24, 5], // stay left
    [25, 20], // merge
    [26, 10], // roundabout enter
    [27, 11], // roundabout exit
    [28, 17], // ferry enter
    [29, 0], // ferry exit
    [37, 21], // merge right
    [38, 20], // merge left
])

export const ValhallaEngines = new Map([
    ["fossgis_valhalla_car", makeEngine("auto")],
    ["fossgis_valhalla_bicycle", makeEngine("bicycle")],
    ["fossgis_valhalla_foot", makeEngine("pedestrian")],
])
