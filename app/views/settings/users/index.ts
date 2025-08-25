import { configureStandardPagination } from "../../lib/standard-pagination"

const body = document.querySelector("body.settings-users-body")
if (body) {
    configureStandardPagination(body, { reverse: false })

    const exportVisibleBtn = body.querySelector("button.export-visible-btn")
    exportVisibleBtn.addEventListener("click", () => {
        const userIds = Array.from(body.querySelectorAll("tr[data-user-id]")).map(
            (el) => el.dataset.userId,
        )
        const json = `[${userIds.join(",")}]`
        navigator.clipboard.writeText(json)
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
