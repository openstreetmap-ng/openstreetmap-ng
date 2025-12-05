import { primaryLanguage } from "@lib/config"
import { dateTimeFormat, relativeTimeFormat } from "@lib/format"

const resolvedElements = new WeakSet<HTMLTimeElement>()

/**
 * Convert a UTC datetime string to local time format for datetime-local input
 * @param utcDateString - ISO datetime string in UTC (from backend)
 * @returns Local datetime string in 'YYYY-MM-DDTHH:mm' format for datetime-local input
 */
const utcStringToLocalString = (utcDateString: string) => {
    const utcDate = new Date(utcDateString)
    if (Number.isNaN(utcDate.getTime())) return ""

    // Convert to local time and format for datetime-local input
    const year = utcDate.getFullYear()
    const month = String(utcDate.getMonth() + 1).padStart(2, "0")
    const day = String(utcDate.getDate()).padStart(2, "0")
    const hours = String(utcDate.getHours()).padStart(2, "0")
    const minutes = String(utcDate.getMinutes()).padStart(2, "0")

    return `${year}-${month}-${day}T${hours}:${minutes}`
}

/**
 * Convert a local datetime string to UTC format for sending to backend
 * @param localDatetimeString - Local datetime string from datetime-local input
 * @returns ISO datetime string in UTC format
 */
const localStringToUtcString = (localDatetimeString: string) => {
    // Create date object treating the input as local time
    const localDate = new Date(localDatetimeString)
    if (Number.isNaN(localDate.getTime())) return ""

    // Return as UTC ISO string
    return localDate.toISOString()
}

/**
 * Setup timezone conversion for datetime-local inputs in a form.
 * This function:
 * 1. Converts any existing UTC values to local time for display
 * 2. Creates hidden inputs that are automatically updated with UTC values
 * 3. Removes the name attribute from visible inputs to prevent direct submission
 *
 * @param form - The form element containing datetime-local inputs
 * @param datetimeInputNames - Array of input names to handle
 */
export const configureDatetimeInputs = (
    form: HTMLFormElement,
    datetimeInputNames: string[],
) => {
    console.debug("configureDatetimeInputs", datetimeInputNames)

    for (const inputName of datetimeInputNames) {
        const input = form.querySelector(
            `input[type=datetime-local][name="${inputName}"]`,
        )
        if (!input) {
            console.warn("Missing datetime-local input for", inputName)
            continue
        }

        // Remove name from visible input so it doesn't get submitted
        input.removeAttribute("name")

        // Create hidden input that will hold the UTC value for submission
        const hiddenInput = document.createElement("input")
        hiddenInput.type = "hidden"
        hiddenInput.name = inputName
        input.after(hiddenInput)

        // Update hidden input whenever visible input changes
        input.addEventListener("input", () => {
            hiddenInput.value = localStringToUtcString(input.value)
        })

        // Convert existing UTC value to local time for display
        input.value = utcStringToLocalString(
            input.dataset.value ?? input.getAttribute("value"),
        )
        input.dispatchEvent(new Event("input"))
        delete input.dataset.value
    }
}

export const resolveDatetimeLazy = (searchElement: Element) =>
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
                    // @ts-expect-error
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

const TIME_UNITS = [
    [31536000, "year"],
    [2592000, "month"],
    [604800, "week"],
    [86400, "day"],
    [3600, "hour"],
    [60, "minute"],
] as const

const getRelativeFormatValueUnit = (date: Date) => {
    const diff = (date.getTime() - Date.now()) / 1000
    const [secs, unit] = TIME_UNITS.find(([s]) => Math.abs(diff) >= s) ?? [1, "second"]
    return [(diff / secs) | 0, unit] as const
}

// Initial update
resolveDatetimeLazy(document.body)
