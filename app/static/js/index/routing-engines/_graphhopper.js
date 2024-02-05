import * as L from "leaflet"
import { primaryLanguage } from "../../_config.js"
import "../../_types.js"

// GraphHopper API Documentation
// https://docs.graphhopper.com/#tag/Routing-API

const graphhopperApiKey = "LijBPDQGfu7Iiq80w3HzwB4RUDJbMbhs6BU0dEnn"

/**
 * Create a new GraphHopper engine
 * @param {"car"|"bike"|"foot"} profile Routing profile
 */
const makeEngine = (profile) => {
    /**
     * @param {AbortSignal} abortSignal Abort signal
     * @param {object} from From coordinates
     * @param {object} to To coordinates
     * @param {object} options Options
     * @param {function} options.successCallback Success callback
     * @param {function} options.errorCallback Error callback
     */
    return (abortSignal, from, to, { successCallback, errorCallback }) => {
        fetch(`https://graphhopper.com/api/1/route?key=${graphhopperApiKey}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                profile: profile,
                points: [from, to],
                locale: primaryLanguage,
                // biome-ignore lint/style/useNamingConvention: Not controlled by this project
                points_encoded: false,
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
                const path = data.paths[0]
                const points = path.points.coordinates
                const steps = []

                for (const instr of path.instructions) {
                    const instrPoints = points.slice(instr.interval[0], instr.interval[1] + 1)
                    const [lon, lat] = instrPoints[0]
                    steps.push({
                        lon: lon,
                        lat: lat,
                        line: L.polyline(instrPoints),
                        distance: instr.distance,
                        time: instr.time / 1000,
                        code: signToCodeMap.get(instr.sign) ?? 0,
                        text: instr.text,
                    })
                }

                const route = {
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

const signToCodeMap = new Map([
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
])

export const GraphHopperEngines = new Map([
    ["graphhopper_car", makeEngine("car")],
    ["graphhopper_bicycle", makeEngine("bike")],
    ["graphhopper_foot", makeEngine("foot")],
])
