const resolvedElements: WeakSet<HTMLTimeElement> = new WeakSet()

export const resolveDatetime = (elements: NodeListOf<HTMLTimeElement>): void => {
    console.debug("Resolving", elements.length, "datetime elements")
    for (const element of elements) {
        if (resolvedElements.has(element)) continue
        resolvedElements.add(element)
        const datetime = element.getAttribute("datetime")
        if (!datetime) {
            console.warn("Missing datetime attribute on", element)
            continue
        }
        const date = Date.parse(datetime)
        const dataset = element.dataset
        const dateStyle = dataset.date
        const timeStyle = dataset.time
        if (dateStyle || timeStyle) {
            // Absolute date
            // @ts-ignore
            element.textContent = Intl.DateTimeFormat(undefined, {
                dateStyle: dateStyle,
                timeStyle: timeStyle,
            }).format(date)
            element.title = Intl.DateTimeFormat(undefined, {
                dateStyle: "long",
                timeStyle: "long",
            }).format(date)
        }
    }
}

// Initial update
resolveDatetime(document.querySelectorAll("time[datetime]"))
