import { decode } from "@mapbox/polyline"
import { graphhopperApiKey } from "../../_api-keys"
import { primaryLanguage } from "../../_config"
import "../../_types"
import type { LonLat } from "../../leaflet/_map-utils"
import type { RoutingEngine, RoutingRoute, RoutingStep } from "../_routing"

// GraphHopper API Documentation
// https://docs.graphhopper.com/#tag/Routing-API

/** Create a new GraphHopper engine */
const makeEngine = (profile: "car" | "bike" | "foot"): RoutingEngine => {
    return (
        abortSignal: AbortSignal,
        from: LonLat,
        to: LonLat,
        successCallback: (route: RoutingRoute) => void,
        errorCallback: (error: Error) => void,
    ): void => {
        fetch(`https://graphhopper.com/api/1/route?key=${graphhopperApiKey}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                profile: profile,
                points: [
                    [from.lon, from.lat],
                    [to.lon, to.lat],
                ],
                locale: primaryLanguage,
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
                    if (data.message) {
                        throw new Error(`${data.message} (${resp.status})`)
                    }
                    throw new Error(`${resp.status} ${resp.statusText}`)
                }

                const path = data.paths[0]
                const points = decode(path.points, 5)
                const steps: RoutingStep[] = []

                for (const instr of path.instructions) {
                    const instrPoints = points.slice(instr.interval[0], instr.interval[1] + 1)
                    steps.push({
                        geom: instrPoints,
                        distance: instr.distance,
                        time: instr.time / 1000,
                        code: signToCodeMap.get(instr.sign) ?? 0,
                        text: instr.text,
                    })
                }

                const route: RoutingRoute = {
                    steps: steps,
                    attribution: '<a href="https://www.graphhopper.com" target="_blank">GraphHopper</a>',
                    ascend: path.ascend,
                    descend: path.descend,
                }
                successCallback(route)
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch graphhopper route", error)
                errorCallback(error)
            })
    }
}

const signToCodeMap: Map<number, number> = new Map([
    [-98, 4], // u-turn
    [-8, 4], // left u-turn
    [-7, 19], // keep left
    [-3, 7], // sharp left
    [-2, 6], // left
    [-1, 5], // slight left
    [0, 0], // straight
    [1, 1], // slight right
    [2, 2], // right
    [3, 3], // sharp right
    [4, 14], // finish reached
    [5, 14], // via reached
    [6, 10], // roundabout
    [7, 18], // keep right
    [8, 4], // right u-turn
])

export const GraphHopperEngines: Map<string, RoutingEngine> = new Map([
    ["graphhopper_car", makeEngine("car")],
    ["graphhopper_bicycle", makeEngine("bike")],
    ["graphhopper_foot", makeEngine("foot")],
])
