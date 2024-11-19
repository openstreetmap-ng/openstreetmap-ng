import { primaryLanguage } from "./_config"

const resolvedElements: WeakSet<HTMLTimeElement> = new WeakSet()

export const resolveDatetime = (searchElement: Element): void => {
    const elements = searchElement.querySelectorAll("time[datetime]")
    console.debug("Resolving", elements.length, "datetime elements")
    for (const element of elements) {
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
            element.textContent = Intl.DateTimeFormat(primaryLanguage, {
                dateStyle: dateStyle,
                timeStyle: timeStyle,
            }).format(date)
            element.title = Intl.DateTimeFormat(primaryLanguage, {
                dateStyle: dateStyle ? "long" : undefined,
                timeStyle: timeStyle ? "long" : undefined,
            }).format(date)
        } else if (style) {
            // Relative date
            const [diff, unit] = getRelativeFormatValueUnit(date)
            element.textContent = new Intl.RelativeTimeFormat(primaryLanguage, {
                // @ts-ignore
                style: style,
            }).format(diff, unit)
            element.title = Intl.DateTimeFormat(primaryLanguage, {
                dateStyle: "long",
                timeStyle: "long",
            }).format(date)
        }
    }
}

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
resolveDatetime(window.document.body)
