import { decode } from "@mapbox/polyline"
import i18next from "i18next"
import { qsEncode } from "../../_qs"
import "../../_types"
import type { LonLat } from "../../leaflet/_map-utils"
import type { RoutingEngine, RoutingRoute, RoutingStep } from "../_routing"

// OSRM API Documentation
// https://project-osrm.org/docs/v5.24.0/api/#route-service

/** Create a new OSRM engine */
const makeEngine = (profile: "car" | "bike" | "foot"): RoutingEngine => {
    return (
        abortSignal: AbortSignal,
        from: LonLat,
        to: LonLat,
        successCallback: (route: RoutingRoute) => void,
        errorCallback: (error: Error) => void,
    ): void => {
        const queryString = qsEncode({
            steps: "true", // returned route steps for each route leg
            geometries: "polyline6", // polyline encoding with 6 digits precision
            overview: "false", // no overview (simplified according to highest zoom level)
        })

        fetch(
            `https://router.project-osrm.org/route/v1/${profile}/${from.lon},${from.lat};${to.lon},${to.lat}?${queryString}`,
            {
                method: "GET",
                mode: "cors",
                credentials: "omit",
                cache: "no-store",
                signal: abortSignal,
                priority: "high",
            },
        )
            .then(async (resp) => {
                const data = await resp.json()

                if (!resp.ok) {
                    if (data.message && data.code) {
                        throw new Error(`${data.message} (${data.code})`)
                    }
                    throw new Error(`${resp.status} ${resp.statusText}`)
                }

                const leg = data.routes[0].legs[0]
                const steps: RoutingStep[] = []

                for (const step of leg.steps) {
                    const stepPoints = decode(step.geometry, 6)
                    const maneuverId = getManeuverId(step.maneuver)
                    steps.push({
                        geom: stepPoints,
                        distance: step.distance,
                        time: step.duration,
                        code: maneuverIdToCodeMap.get(maneuverId) ?? 0,
                        text: getStepText(step, maneuverId),
                    })
                }

                const route: RoutingRoute = {
                    steps: steps,
                    attribution:
                        '<a href="https://routing.openstreetmap.de/about.html" target="_blank">OSRM (FOSSGIS)</a>',
                    ascend: null,
                    descend: null,
                }
                successCallback(route)
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch osrm route", error)
                errorCallback(error)
            })
    }
}

const getManeuverId = ({ type, modifier }: { type: string; modifier: string }): string => {
    switch (type) {
        case "on ramp":
        case "off ramp":
        case "merge":
        case "end of road":
        case "fork":
            return `${type} ${modifier.indexOf("left") >= 0 ? "left" : "right"}`
        case "depart":
        case "arrive":
        case "rotary":
        case "roundabout":
        case "exit rotary":
        case "exit roundabout":
            return type
        // case "roundabout turn":
        // case "turn":
        default:
            return `turn ${modifier}`
    }
}

const getStepText = (step: any, maneuverId: string): string => {
    const stepName = step.name
    const stepRef = step.ref
    const translation = maneuverIdToTranslation.get(maneuverId)

    let name: string
    let isOwnName: boolean
    if (stepName && stepRef) {
        name = `${stepName} (${stepRef})`
        isOwnName = true
    } else if (step.name) {
        name = stepName
        isOwnName = true
    } else if (step.ref) {
        name = stepRef
        isOwnName = true
    } else {
        name = i18next.t("javascripts.directions.instructions.unnamed")
        isOwnName = false
    }

    if (maneuverId === "exit rotary" || maneuverId === "exit roundabout") {
        return i18next.t(translation, { name })
    }

    if (maneuverId === "rotary" || maneuverId === "roundabout") {
        const stepManeuverExit = step.maneuver.exit
        if (!stepManeuverExit) {
            return i18next.t(`${translation}_without_exit`, { name })
        }

        if (stepManeuverExit <= 10) {
            const exitTranslation = maneuverExitToTranslation.get(stepManeuverExit)
            return i18next.t(`${translation}_with_exit_ordinal`, { name, exit: i18next.t(exitTranslation) })
        }

        // stepManeuverExit >= 11
        return i18next.t(`${translation}_with_exit`, { name, exit: stepManeuverExit })
    }

    if (
        maneuverId === "on ramp left" ||
        maneuverId === "on ramp right" ||
        maneuverId === "off ramp left" ||
        maneuverId === "off ramp right"
    ) {
        let withStr = "_with"
        const params: { [key: string]: string } = {}

        if (step.exits && (maneuverId === "off ramp left" || maneuverId === "off ramp right")) {
            withStr += "_exit"
            params.exit = step.exits
        }

        if (isOwnName) {
            withStr += "_name"
            params.name = name
        }

        if (step.destinations) {
            withStr += "_directions"
            params.directions = step.destinations
        }

        // Perform simple translation if no parameters
        if (!Object.keys(params).length) {
            return i18next.t(translation)
        }

        return i18next.t(translation + withStr, params)
    }

    return i18next.t(`${translation}_without_exit`, { name })
}

const maneuverIdToCodeMap: Map<string, number> = new Map([
    ["continue", 0],
    ["merge right", 21],
    ["merge left", 20],
    ["off ramp right", 24],
    ["off ramp left", 25],
    ["on ramp right", 2],
    ["on ramp left", 6],
    ["fork right", 18],
    ["fork left", 19],
    ["end of road right", 22],
    ["end of road left", 23],
    ["turn straight", 0],
    ["turn slight right", 1],
    ["turn right", 2],
    ["turn sharp right", 3],
    ["turn uturn", 4],
    ["turn slight left", 5],
    ["turn left", 6],
    ["turn sharp left", 7],
    ["roundabout", 10],
    ["rotary", 10],
    ["exit roundabout", 10],
    ["exit rotary", 10],
    ["depart", 8],
    ["arrive", 14],
])

const maneuverIdToTranslation: Map<string, string> = new Map([
    ["continue", "javascripts.directions.instructions.continue"],
    ["merge right", "javascripts.directions.instructions.merge_right"],
    ["merge left", "javascripts.directions.instructions.merge_left"],
    ["off ramp right", "javascripts.directions.instructions.offramp_right"],
    ["off ramp left", "javascripts.directions.instructions.offramp_left"],
    ["on ramp right", "javascripts.directions.instructions.onramp_right"],
    ["on ramp left", "javascripts.directions.instructions.onramp_left"],
    ["fork right", "javascripts.directions.instructions.fork_right"],
    ["fork left", "javascripts.directions.instructions.fork_left"],
    ["end of road right", "javascripts.directions.instructions.endofroad_right"],
    ["end of road left", "javascripts.directions.instructions.endofroad_left"],
    ["turn straight", "javascripts.directions.instructions.continue"],
    ["turn slight right", "javascripts.directions.instructions.slight_right"],
    ["turn right", "javascripts.directions.instructions.turn_right"],
    ["turn sharp right", "javascripts.directions.instructions.sharp_right"],
    ["turn uturn", "javascripts.directions.instructions.uturn"],
    ["turn sharp left", "javascripts.directions.instructions.sharp_left"],
    ["turn left", "javascripts.directions.instructions.turn_left"],
    ["turn slight left", "javascripts.directions.instructions.slight_left"],
    ["roundabout", "javascripts.directions.instructions.roundabout"],
    ["rotary", "javascripts.directions.instructions.roundabout"],
    ["exit roundabout", "javascripts.directions.instructions.exit_roundabout"],
    ["exit rotary", "javascripts.directions.instructions.exit_roundabout"],
    ["depart", "javascripts.directions.instructions.start"],
    ["arrive", "javascripts.directions.instructions.destination"],
])

const maneuverExitToTranslation: Map<number, string> = new Map([
    [1, "javascripts.directions.instructions.exit_counts.first"],
    [2, "javascripts.directions.instructions.exit_counts.second"],
    [3, "javascripts.directions.instructions.exit_counts.third"],
    [4, "javascripts.directions.instructions.exit_counts.fourth"],
    [5, "javascripts.directions.instructions.exit_counts.fifth"],
    [6, "javascripts.directions.instructions.exit_counts.sixth"],
    [7, "javascripts.directions.instructions.exit_counts.seventh"],
    [8, "javascripts.directions.instructions.exit_counts.eighth"],
    [9, "javascripts.directions.instructions.exit_counts.ninth"],
    [10, "javascripts.directions.instructions.exit_counts.tenth"],
])

export const OSRMEngines: Map<string, RoutingEngine> = new Map([
    ["fossgis_osrm_car", makeEngine("car")],
    ["fossgis_osrm_bike", makeEngine("bike")],
    ["fossgis_osrm_foot", makeEngine("foot")],
])
