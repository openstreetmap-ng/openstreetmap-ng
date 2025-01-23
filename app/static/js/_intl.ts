import { memoize, staticCache } from "./_utils.ts"

export const dateTimeFormat = memoize(
    (...args: ConstructorParameters<typeof Intl.DateTimeFormat>) => new Intl.DateTimeFormat(...args),
)

export const relativeTimeFormat = memoize(
    (...args: ConstructorParameters<typeof Intl.RelativeTimeFormat>) => new Intl.RelativeTimeFormat(...args),
)

/** Get the current timezone name */
export const timeZoneName = staticCache(() => {
    const result = dateTimeFormat().resolvedOptions().timeZone
    console.debug("Current timezone name", result)
    return result
})

const isImperialLanguage = (): boolean => navigator.language.startsWith("en-US") || navigator.language.startsWith("my")
const isImperialRegion = (): boolean => {
    const timezoneName = timeZoneName()
    return (
        timezoneName.startsWith("America/") || // United States and territories
        timezoneName === "Asia/Yangon" || // Myanmar (Burma)
        timezoneName === "Africa/Monrovia" // Liberia
    )
}

/** User preference for metric units */
export const isMetricUnit = staticCache(() => {
    const result = !(isImperialLanguage() && isImperialRegion())
    console.debug("Is using metric units?", isMetricUnit)
    return result
})
