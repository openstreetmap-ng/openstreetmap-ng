import { primaryLanguage } from "./_config"
import { dateTimeFormat, relativeTimeFormat } from "./_intl.ts"

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
            const dateStyle = dataset.date as any
            const timeStyle = dataset.time as any
            const style = dataset.style
            if (dateStyle || timeStyle) {
                // Absolute date
                // @ts-ignore
                element.textContent = dateTimeFormat(primaryLanguage, {
                    dateStyle: dateStyle,
                    timeStyle: timeStyle,
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
        console.debug("Resolved", absoluteCounter, "absolute and", relativeCounter, "relative datetimes")
    })

const getRelativeFormatValueUnit = (date: Date): [number, Intl.RelativeTimeFormatUnitSingular] => {
    let diff = (date.getTime() - Date.now()) / 1000
    let unit: Intl.RelativeTimeFormatUnitSingular
    const diffAbs = Math.abs(diff)
    if (diffAbs < 60) {
        unit = "second"
    } else if (diffAbs < 3600) {
        diff /= 60
        unit = "minute"
    } else if (diffAbs < 3600 * 24) {
        diff /= 3600
        unit = "hour"
    } else if (diffAbs < 3600 * 24 * 7) {
        diff /= 3600 * 24
        unit = "day"
    } else if (diffAbs < 3600 * 24 * 30) {
        diff /= 3600 * 24 * 7
        unit = "week"
    } else if (diffAbs < 3600 * 24 * 365) {
        diff /= 3600 * 24 * 30
        unit = "month"
    } else {
        diff /= 3600 * 24 * 365
        unit = "year"
    }
    // Round down
    diff = diff < 0 ? Math.ceil(diff) : Math.floor(diff)
    return [diff, unit]
}

// Initial update
resolveDatetimeLazy(window.document.body)
