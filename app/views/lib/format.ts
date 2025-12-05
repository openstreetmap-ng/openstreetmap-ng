import { primaryLanguage } from "@lib/config"
import { memoize } from "@lib/memoize"
import i18next from "i18next"

type LonLat = { lon: number; lat: number }

export const dateTimeFormat = memoize(
    (...args: ConstructorParameters<typeof Intl.DateTimeFormat>) =>
        new Intl.DateTimeFormat(...args),
)

export const relativeTimeFormat = memoize(
    (...args: ConstructorParameters<typeof Intl.RelativeTimeFormat>) =>
        new Intl.RelativeTimeFormat(...args),
)

export const formatShortDate = (dateIso: string): string =>
    dateTimeFormat(primaryLanguage, {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
    }).format(new Date(dateIso))

export const formatMonthName = (
    dateIso: string,
    month: Intl.DateTimeFormatOptions["month"],
): string =>
    dateTimeFormat(primaryLanguage, {
        month: month,
        timeZone: "UTC",
    }).format(new Date(dateIso))

export const formatWeekdayName = (
    dateIso: string,
    weekday: Intl.DateTimeFormatOptions["weekday"],
): string =>
    dateTimeFormat(primaryLanguage, {
        weekday: weekday,
        timeZone: "UTC",
    }).format(new Date(dateIso))

export const getTimezoneName = memoize(() => {
    const result = dateTimeFormat().resolvedOptions().timeZone
    console.debug("Current timezone name", result)
    return result
})

const isImperialLanguage = (language: string): boolean =>
    language.startsWith("en-US") ||
    language.startsWith("en-GB") ||
    language.startsWith("my")

const isImperialRegion = (timezoneName: string): boolean =>
    timezoneName.startsWith("America/") ||
    timezoneName === "Europe/London" ||
    timezoneName === "Asia/Yangon" ||
    timezoneName === "Africa/Monrovia"

export const isMetricUnit = memoize(() => {
    const language = navigator.language
    const timezoneName = getTimezoneName()
    const result = !(isImperialLanguage(language) && isImperialRegion(timezoneName))
    console.debug(
        "Using",
        result ? "metric" : "imperial",
        "units for",
        language,
        "in",
        timezoneName,
    )
    return result
})

export const formatDistance = (
    meters: number,
    unit: "metric" | "imperial" = "metric",
): string => {
    if (unit === "imperial") {
        const feet = meters * 3.28084
        if (feet < 1000) {
            return i18next.t("distance.feet", {
                distance: Math.round(feet),
            })
        }
        const miles = meters * 0.000621371
        return i18next.t("distance.miles", {
            distance: miles.toFixed(miles < 10 ? 1 : 0),
        })
    }

    const km = meters / 1000
    if (km < 1)
        return i18next.t("javascripts.directions.distance_m", {
            distance: Math.round(meters),
        })
    return i18next.t("javascripts.directions.distance_km", {
        distance: km.toFixed(km < 10 ? 1 : 0),
    })
}

export const formatDistanceRounded = (
    meters: number,
    unit: "metric" | "imperial" = "metric",
): string => {
    if (unit === "imperial") {
        const feet = meters * 3.28084
        if (feet < 5) return ""
        if (feet < 1000) {
            const precision = feet < 200 ? 10 : feet < 500 ? 25 : 50
            return i18next.t("distance.feet", {
                distance: Math.round(feet / precision) * precision,
            })
        }
        const miles = meters * 0.000621371
        const digits = miles < 5 ? 1 : 0
        return i18next.t("distance.miles", {
            distance: miles.toFixed(digits),
        })
    }

    if (meters < 5) return ""
    if (meters < 1500) {
        const precision = meters < 200 ? 10 : 100
        return i18next.t("javascripts.directions.distance_m", {
            distance: Math.round(meters / precision) * precision,
        })
    }
    const digits = meters < 5000 ? 1 : 0
    return i18next.t("javascripts.directions.distance_km", {
        distance: (meters / 1000).toFixed(digits),
    })
}

export const formatHeight = (meters: number): string =>
    i18next.t("javascripts.directions.distance_m", {
        distance: Math.round(meters),
    })

export const formatTime = (seconds: number): string => {
    const hours = (seconds / 3600) | 0
    const minutes = ((seconds % 3600) / 60) | 0
    return `${hours}:${minutes.toString().padStart(2, "0")}`
}

const padDegreesComponent = (value: number): string => value.toString().padStart(2, "0")

const formatDegrees = (decimalDegree: number): string => {
    decimalDegree = Math.abs(decimalDegree)
    const deg = decimalDegree | 0
    const minSec = (decimalDegree - deg) * 60
    const min = minSec | 0
    const sec = ((minSec - min) * 60) | 0
    return `${padDegreesComponent(deg)}°${padDegreesComponent(min)}′${padDegreesComponent(sec)}″`
}

export const formatCoordinate = ({ lon, lat }: LonLat): string => {
    const latDir = lat === 0 ? "" : lat > 0 ? "N" : "S"
    const lonDir = lon === 0 ? "" : lon > 0 ? "E" : "W"
    return `${formatDegrees(lat)}${latDir} ${formatDegrees(lon)}${lonDir}`
}
