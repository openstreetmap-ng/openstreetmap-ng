import { startsWith as bytesStartsWith } from "@std/bytes/starts-with"
import { memoize } from "@std/cache/memoize"
import { SECOND } from "@std/datetime/constants"
import { format as formatDatetime } from "@std/datetime/format"
import { parse as parseDatetime } from "@std/datetime/parse"
import { primaryLanguage } from "@utils/config"
import { t } from "i18next"

type LonLat = { lon: number; lat: number }

const DATETIME_LOCAL_FORMAT = "yyyy-MM-dd'T'HH:mm"

export const unixToLocalDatetime = (unix: bigint | number | undefined) => {
  if (unix === undefined) return ""
  return formatDatetime(new Date(Number(unix) * SECOND), DATETIME_LOCAL_FORMAT)
}

export const localDatetimeToUnix = (value: string) =>
  value
    ? BigInt(Math.floor(parseDatetime(value, DATETIME_LOCAL_FORMAT).getTime() / SECOND))
    : undefined

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

// NOTE: ideally we should fix translations
const _STRIP_SPECIAL_RE = /^[!?:;., ]+|[!?:;., ]+$/g
export const stripSpecial = (value: string) => value.replace(_STRIP_SPECIAL_RE, "")

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
  const hours = Math.trunc(seconds / 3600)
  const minutes = Math.trunc((seconds % 3600) / 60)
  return `${hours}:${minutes.toString().padStart(2, "0")}`
}

const LATIN1_DECODER = new TextDecoder("latin1")

export const encodeAscii = (bytes: Uint8Array) => LATIN1_DECODER.decode(bytes)

export const headersDate = (headers: Headers | null) => {
  const ms = Date.parse(headers?.get("date") ?? "")
  return BigInt(Math.trunc((Number.isNaN(ms) ? Date.now() : ms) / SECOND))
}

const padDegreesComponent = (value: number) => value.toString().padStart(2, "0")

const formatDegrees = (decimalDegree: number) => {
  decimalDegree = Math.abs(decimalDegree)
  const deg = Math.trunc(decimalDegree)
  const minSec = (decimalDegree - deg) * 60
  const min = Math.trunc(minSec)
  const sec = Math.trunc((minSec - min) * 60)
  return `${padDegreesComponent(deg)}°${padDegreesComponent(min)}′${padDegreesComponent(sec)}″`
}

export const formatCoordinate = ({ lon, lat }: LonLat) => {
  const latDir = lat === 0 ? "" : lat > 0 ? "N" : "S"
  const lonDir = lon === 0 ? "" : lon > 0 ? "E" : "W"
  return `${formatDegrees(lat)}${latDir} ${formatDegrees(lon)}${lonDir}`
}

const IPV4_MAPPED_IPV6_PREFIX = Uint8Array.of(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff)

const formatIpv4 = (bytes: Uint8Array, offset = 0) =>
  `${bytes[offset]}.${bytes[offset + 1]}.${bytes[offset + 2]}.${bytes[offset + 3]}`

export const formatPackedIp = (packedIp: Uint8Array) => {
  if (packedIp.length === 2) return `${packedIp[0]}.${packedIp[1]}.*.*`

  if (packedIp.length === 3) {
    if (packedIp[0] !== 0xff)
      throw new Error(`Unexpected packed IP length: ${packedIp.length}`)
    return `::ffff:${packedIp[1]}.${packedIp[2]}.*.*`
  }

  if (packedIp.length === 4) return formatIpv4(packedIp)

  if (packedIp.length === 6) {
    const groups = Array.from(
      { length: 3 },
      (_, i) => (packedIp[i * 2]! << 8) | packedIp[i * 2 + 1]!,
    )
    return `${groups[0]!.toString(16)}:${groups[1]!.toString(16)}:${groups[2]!.toString(16)}:*:*:*:*:*`
  }

  if (packedIp.length !== 16)
    throw new Error(`Unexpected packed IP length: ${packedIp.length}`)

  if (bytesStartsWith(packedIp, IPV4_MAPPED_IPV6_PREFIX))
    return `::ffff:${formatIpv4(packedIp, 12)}`

  const groups = Array.from(
    { length: 8 },
    (_, i) => (packedIp[i * 2]! << 8) | packedIp[i * 2 + 1]!,
  )
  let bestStart = -1
  let bestLen = 0
  let currentStart = -1
  let currentLen = 0

  for (let i = 0; i <= groups.length; i++) {
    if (i < groups.length && groups[i] === 0) {
      if (currentStart === -1) currentStart = i
      currentLen += 1
      continue
    }
    if (currentLen >= 2 && currentLen > bestLen) {
      bestStart = currentStart
      bestLen = currentLen
    }
    currentStart = -1
    currentLen = 0
  }

  if (bestStart === -1) return groups.map((group) => group.toString(16)).join(":")

  const head = groups
    .slice(0, bestStart)
    .map((group) => group.toString(16))
    .join(":")
  const tail = groups
    .slice(bestStart + bestLen)
    .map((group) => group.toString(16))
    .join(":")
  if (!head && !tail) return "::"
  if (!head) return `::${tail}`
  if (!tail) return `${head}::`
  return `${head}::${tail}`
}
