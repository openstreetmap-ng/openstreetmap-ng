import { primaryLanguage } from "./config"
import { dateTimeFormat, relativeTimeFormat } from "./intl"

const resolvedElements: WeakSet<HTMLTimeElement> = new WeakSet()

export const resolveDatetimeLazy = (searchElement: Element): void =>
    queueMicrotask(() => {
        let absoluteCounter = 0
        let relativeCounter = 0
        for (const element of searchElement.querySelectorAll("time[datetime]")) {
            if (resolvedElements.has(element)) continue
            resolvedElements.add(element)
            const datetime = element.getAttribute("datetime")
            if (!datetime) {
                console.warn("Missing datetime attribute on", element)
                continue
            }
            const date = new Date(datetime)
            const dataset = element.dataset
            const dateStyle = dataset.date
            const timeStyle = dataset.time
            const style = dataset.style
            if (dateStyle || timeStyle) {
                // Absolute date
                // @ts-ignore
                element.textContent = dateTimeFormat(primaryLanguage, {
                    dateStyle: dateStyle as any,
                    timeStyle: timeStyle as any,
                }).format(date)
                element.title = dateTimeFormat(primaryLanguage, {
                    dateStyle: dateStyle ? "long" : undefined,
                    timeStyle: timeStyle ? "long" : undefined,
                }).format(date)
                absoluteCounter++
            } else if (style) {
                // Relative date
                const [diff, unit] = getRelativeFormatValueUnit(date)
                element.textContent = relativeTimeFormat(primaryLanguage, {
                    // @ts-ignore
                    style: style,
                }).format(diff, unit)
                element.title = dateTimeFormat(primaryLanguage, {
                    dateStyle: "long",
                    timeStyle: "long",
                }).format(date)
                relativeCounter++
            }
        }
        console.debug(
            "Resolved",
            absoluteCounter,
            "absolute and",
            relativeCounter,
            "relative datetimes",
        )
    })

const getRelativeFormatValueUnit = (
    date: Date,
): [number, Intl.RelativeTimeFormatUnitSingular] => {
    const diffSeconds = (date.getTime() - Date.now()) / 1000
    const diffAbs = Math.abs(diffSeconds)
    if (diffAbs >= 31536000) return [(diffSeconds / 31536000) | 0, "year"]
    if (diffAbs >= 2592000) return [(diffSeconds / 2592000) | 0, "month"]
    if (diffAbs >= 604800) return [(diffSeconds / 604800) | 0, "week"]
    if (diffAbs >= 86400) return [(diffSeconds / 86400) | 0, "day"]
    if (diffAbs >= 3600) return [(diffSeconds / 3600) | 0, "hour"]
    if (diffAbs >= 60) return [(diffSeconds / 60) | 0, "minute"]
    return [diffSeconds | 0, "second"]
}

// Initial update
resolveDatetimeLazy(window.document.body)
