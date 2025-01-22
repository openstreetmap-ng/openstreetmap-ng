const isImperialLanguage = (): boolean => navigator.language.startsWith("en-US") || navigator.language.startsWith("my")

const isImperialRegion = (): boolean => {
    const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone
    return (
        timezoneName.startsWith("America/") || // United States and territories
        timezoneName === "Asia/Yangon" || // Myanmar (Burma)
        timezoneName === "Africa/Monrovia" // Liberia
    )
}

/** User preference for metric units */
export const isMetricUnit = !(isImperialLanguage() && isImperialRegion())
console.debug("Is using metric units?", isMetricUnit)
