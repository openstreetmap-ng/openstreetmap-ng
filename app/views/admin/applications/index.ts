import { Popover, Tooltip } from "bootstrap"
import { configureDatetimeInputs } from "../../lib/datetime"
import { configureStandardPagination } from "../../lib/standard-pagination"

const body = document.querySelector("body.admin-applications-body")
if (body) {
    const filterForm = body.querySelector("form.filters-form")

    // Setup datetime input timezone conversion
    configureDatetimeInputs(filterForm, ["created_after", "created_before"])

    // Disable empty inputs before form submission to prevent validation errors
    filterForm.addEventListener("submit", () => {
        const inputs = filterForm.querySelectorAll("input, select")
        for (const input of inputs) {
            if (!input.value) input.disabled = true
        }
    })

    const exportVisibleBtn = body.querySelector("button.export-visible-btn")
    exportVisibleBtn.addEventListener("click", async () => {
        const appIds = Array.from(body.querySelectorAll("tr[data-app-id]")).map(
            (el) => el.dataset.appId,
        )
        const json = `[${appIds.join(",")}]`

        try {
            await navigator.clipboard.writeText(json)
        } catch (error) {
            console.warn("Failed to copy app IDs", error)
            if (error instanceof Error) alert(error.message)
        }
    })

    const exportAllBtn = body.querySelector("button.export-all-btn")
    exportAllBtn.addEventListener("click", () => {
        const a = document.createElement("a")
        a.href = `/api/web/admin/applications/export${window.location.search}`
        a.download = ""
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
    })

    configureStandardPagination(body, {
        reverse: false,
        loadCallback: (renderContainer) => {
            for (const element of renderContainer.querySelectorAll(
                "[data-bs-toggle=tooltip]",
            )) {
                new Tooltip(element)
            }

            for (const element of renderContainer.querySelectorAll(
                "[data-bs-toggle=popover]",
            )) {
                new Popover(element)
            }
        },
    })
}
