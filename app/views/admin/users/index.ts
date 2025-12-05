import { configureDatetimeInputs } from "@lib/datetime-inputs"
import { mount } from "@lib/mount"
import { configureStandardPagination } from "@lib/standard-pagination"
import { Tooltip } from "bootstrap"

mount("admin-users-body", (body) => {
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
        const userIds = Array.from(
            body.querySelectorAll("tr[data-user-id]"),
            (el) => el.dataset.userId,
        )
        const json = `[${userIds.join(",")}]`

        try {
            await navigator.clipboard.writeText(json)
        } catch (error) {
            console.warn("Failed to copy user IDs", error)
            alert(error.message)
        }
    })

    const exportAllBtn = body.querySelector("button.export-all-btn")
    exportAllBtn.addEventListener("click", () => {
        const a = document.createElement("a")
        a.href = `/api/web/admin/users/export${window.location.search}`
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
        },
    })
})
