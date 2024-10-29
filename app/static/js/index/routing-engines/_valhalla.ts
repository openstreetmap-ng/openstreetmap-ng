import { decode } from "@mapbox/polyline"
import { primaryLanguage } from "../../_config"
import "../../_types"
import type { LonLat } from "../../leaflet/_map-utils"
import type { RoutingEngine, RoutingRoute, RoutingStep } from "../_routing"

// Valhalla API Documentation
// https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/

/** Create a new Valhalla engine */
const makeEngine = (costing: "auto" | "bicycle" | "pedestrian"): RoutingEngine => {
    return (
        abortSignal: AbortSignal,
        from: LonLat,
        to: LonLat,
        successCallback: (route: RoutingRoute) => void,
        errorCallback: (error: Error) => void,
    ): void => {
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
            mode: "cors",
            credentials: "omit",
            cache: "no-store",
            signal: abortSignal,
            priority: "high",
        })
            .then(async (resp) => {
                const data = await resp.json()

                if (!resp.ok) {
                    if (data.error && data.error_code) {
                        throw new Error(`${data.error} (${data.error_code})`)
                    }
                    throw new Error(`${resp.status} ${resp.statusText}`)
                }

                const leg = data.trip.legs[0]
                const points = decode(leg.shape, 6)
                const steps: RoutingStep[] = []

                for (const man of leg.maneuvers) {
                    const manPoints = points.slice(man.begin_shape_index, man.end_shape_index + 1)
                    steps.push({
                        geom: manPoints,
                        distance: man.length * 1000,
                        time: man.time,
                        code: maneuverTypeToCodeMap.get(man.type) ?? 0,
                        text: man.instruction,
                    })
                }

                const route: RoutingRoute = {
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

const maneuverTypeToCodeMap: Map<number, number> = new Map([
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

export const ValhallaEngines: Map<string, RoutingEngine> = new Map([
    ["fossgis_valhalla_car", makeEngine("auto")],
    ["fossgis_valhalla_bicycle", makeEngine("bicycle")],
    ["fossgis_valhalla_foot", makeEngine("pedestrian")],
])
