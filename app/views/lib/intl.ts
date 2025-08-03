import { memoize, staticCache } from "./utils"

export const dateTimeFormat = memoize(
    (...args: ConstructorParameters<typeof Intl.DateTimeFormat>) =>
        new Intl.DateTimeFormat(...args),
)

export const relativeTimeFormat = memoize(
    (...args: ConstructorParameters<typeof Intl.RelativeTimeFormat>) =>
        new Intl.RelativeTimeFormat(...args),
)

/** Get the current timezone name */
export const getTimezoneName = staticCache(() => {
    const result = dateTimeFormat().resolvedOptions().timeZone
    console.debug("Current timezone name", result)
    return result
})

const isImperialLanguage = (language: string): boolean => {
    return (
        language.startsWith("en-US") ||
        language.startsWith("en-GB") ||
        language.startsWith("my")
    )
}
const isImperialRegion = (timezoneName: string): boolean => {
    return (
        timezoneName.startsWith("America/") || // United States and territories
        timezoneName === "Europe/London" || // United Kingdom
        timezoneName === "Asia/Yangon" || // Myanmar (Burma)
        timezoneName === "Africa/Monrovia" // Liberia
    )
}

/** User preference for metric units */
export const isMetricUnit = staticCache(() => {
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
