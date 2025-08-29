import { configureStandardPagination } from "../../lib/standard-pagination"

const body = document.querySelector("body.settings-users-body")
if (body) {
    configureStandardPagination(body, { reverse: false })

    // Disable empty inputs before form submission to prevent validation errors
    const filterForm = body.querySelector("form.filters-form")
    filterForm.addEventListener("submit", () => {
        const inputs = filterForm.querySelectorAll("input, select")
        for (const input of inputs) {
            if (!input.value) input.disabled = true
        }
    })

    const exportVisibleBtn = body.querySelector("button.export-visible-btn")
    exportVisibleBtn.addEventListener("click", async () => {
        const userIds = Array.from(body.querySelectorAll("tr[data-user-id]")).map(
            (el) => el.dataset.userId,
        )
        const json = `[${userIds.join(",")}]`

        try {
            await navigator.clipboard.writeText(json)
        } catch (error) {
            console.warn("Failed to copy user IDs", error)
            if (error instanceof Error) alert(error.message)
        }
    })

    const exportAllBtn = body.querySelector("button.export-all-btn")
    exportAllBtn.addEventListener("click", () => {
        const a = document.createElement("a")
        const params = new URLSearchParams(window.location.search)
        a.href = `/api/web/settings/users/export?${params.toString()}`
        a.download = ""
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
    })
}
