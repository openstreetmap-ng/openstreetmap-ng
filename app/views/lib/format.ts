import { primaryLanguage } from "@lib/config"
import { memoize } from "@std/cache/memoize"
import { t } from "i18next"

type LonLat = { lon: number; lat: number }

export const dateTimeFormat = memoize(
  (...args: ConstructorParameters<typeof Intl.DateTimeFormat>) =>
    new Intl.DateTimeFormat(...args),
  { getKey: (...args) => JSON.stringify(args) },
)

export const relativeTimeFormat = memoize(
  (...args: ConstructorParameters<typeof Intl.RelativeTimeFormat>) =>
    new Intl.RelativeTimeFormat(...args),
  { getKey: (...args) => JSON.stringify(args) },
)

export const formatShortDate = (dateIso: string) =>
  dateTimeFormat(primaryLanguage, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(dateIso))

export const formatMonthName = (
  dateIso: string,
  month: Intl.DateTimeFormatOptions["month"],
) =>
  dateTimeFormat(primaryLanguage, {
    month: month,
    timeZone: "UTC",
  }).format(new Date(dateIso))

export const formatWeekdayName = (
  dateIso: string,
  weekday: Intl.DateTimeFormatOptions["weekday"],
) =>
  dateTimeFormat(primaryLanguage, {
    weekday: weekday,
    timeZone: "UTC",
  }).format(new Date(dateIso))

export const getTimezoneName = memoize(() => {
  const result = dateTimeFormat().resolvedOptions().timeZone
  console.debug("Format: Timezone", result)
  return result
})

const isImperialLanguage = (language: string) =>
  language.startsWith("en-US") ||
  language.startsWith("en-GB") ||
  language.startsWith("my")

const isImperialRegion = (timezoneName: string) =>
  timezoneName.startsWith("America/") ||
  timezoneName === "Europe/London" ||
  timezoneName === "Asia/Yangon" ||
  timezoneName === "Africa/Monrovia"

export const isMetricUnit = memoize(() => {
  const language = navigator.language
  const timezoneName = getTimezoneName()
  const result = !(isImperialLanguage(language) && isImperialRegion(timezoneName))
  console.debug("Format: Unit system", result ? "metric" : "imperial", {
    language,
    timezoneName,
  })
  return result
})

export const formatDistance = (
  meters: number,
  unit: "metric" | "imperial" = "metric",
) => {
  if (unit === "imperial") {
    const feet = meters * 3.28084
    if (feet < 1000) {
      return t("distance.feet", {
        distance: Math.round(feet),
      })
    }
    const miles = meters * 0.000621371
    return t("distance.miles", {
      distance: miles.toFixed(miles < 10 ? 1 : 0),
    })
  }

  const km = meters / 1000
  if (km < 1)
    return t("javascripts.directions.distance_m", {
      distance: Math.round(meters),
    })
  return t("javascripts.directions.distance_km", {
    distance: km.toFixed(km < 10 ? 1 : 0),
  })
}

export const formatDistanceRounded = (
  meters: number,
  unit: "metric" | "imperial" = "metric",
) => {
  if (unit === "imperial") {
    const feet = meters * 3.28084
    if (feet < 5) return ""
    if (feet < 1000) {
      const precision = feet < 200 ? 10 : feet < 500 ? 25 : 50
      return t("distance.feet", {
        distance: Math.round(feet / precision) * precision,
      })
    }
    const miles = meters * 0.000621371
    const digits = miles < 5 ? 1 : 0
    return t("distance.miles", {
      distance: miles.toFixed(digits),
    })
  }

  if (meters < 5) return ""
  if (meters < 1500) {
    const precision = meters < 200 ? 10 : 100
    return t("javascripts.directions.distance_m", {
      distance: Math.round(meters / precision) * precision,
    })
  }
  const digits = meters < 5000 ? 1 : 0
  return t("javascripts.directions.distance_km", {
    distance: (meters / 1000).toFixed(digits),
  })
}

export const formatHeight = (meters: number) =>
  t("javascripts.directions.distance_m", {
    distance: Math.round(meters),
  })

export const formatTime = (seconds: number) => {
  const hours = (seconds / 3600) | 0
  const minutes = ((seconds % 3600) / 60) | 0
  return `${hours}:${minutes.toString().padStart(2, "0")}`
}

const padDegreesComponent = (value: number) => value.toString().padStart(2, "0")

const formatDegrees = (decimalDegree: number) => {
  decimalDegree = Math.abs(decimalDegree)
  const deg = decimalDegree | 0
  const minSec = (decimalDegree - deg) * 60
  const min = minSec | 0
  const sec = ((minSec - min) * 60) | 0
  return `${padDegreesComponent(deg)}°${padDegreesComponent(min)}′${padDegreesComponent(sec)}″`
}

export const formatCoordinate = ({ lon, lat }: LonLat) => {
  const latDir = lat === 0 ? "" : lat > 0 ? "N" : "S"
  const lonDir = lon === 0 ? "" : lon > 0 ? "E" : "W"
  return `${formatDegrees(lat)}${latDir} ${formatDegrees(lon)}${lonDir}`
}
