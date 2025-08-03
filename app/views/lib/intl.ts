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

const isImperialLanguage = (): boolean => {
    const language = navigator.language
    return (
        language.startsWith("en-US") ||
        language.startsWith("en-GB") ||
        language.startsWith("my")
    )
}
const isImperialRegion = (): boolean => {
    const timezoneName = getTimezoneName()
    return (
        timezoneName.startsWith("America/") || // United States and territories
        timezoneName === "Europe/London" || // United Kingdom
        timezoneName === "Asia/Yangon" || // Myanmar (Burma)
        timezoneName === "Africa/Monrovia" // Liberia
    )
}

/** User preference for metric units */
export const isMetricUnit = staticCache(() => {
    const result = !(isImperialLanguage() && isImperialRegion())
    console.debug("Using metric units:", result)
    return result
})
