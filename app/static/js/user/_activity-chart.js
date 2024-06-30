import { Tooltip } from "bootstrap"

const table = document.getElementById("activity-table")
const container = document.getElementById("activity-container")

const multiple = container.dataset.multiple
const single = container.dataset.single
const none = container.dataset.none

if (container && table) {
    // resize activity chart when container size changes
    const f = (width) => (container.style.cssText = `--width: ${width}px`)
    new ResizeObserver((entries) => f(entries[0].contentRect.width)).observe(container)
    f(container.offsetWidth) // call on load

    // add tooltips
    table.querySelectorAll('td[class*="activity"]').forEach((element) => {
        const [amount, date] = [+element.dataset.total, element.dataset.date]
        const text = amount === 0 ? none : amount === 1 ? single : multiple.replace("{num}", amount)
        Tooltip.getOrCreateInstance(element, {
            title: text.replace("{date}", date),
            placement: "bottom",
        })
    })
}
