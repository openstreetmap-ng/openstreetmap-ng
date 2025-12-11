import { mount } from "@lib/mount"
import { configureStandardPagination } from "@lib/standard-pagination"

mount("reports-body", (body) => {
    const reportStatusFilter = body.querySelector("select#reportStatusFilter")!
    reportStatusFilter.addEventListener("change", () => {
        const status = reportStatusFilter.value
        console.debug("ReportsIndex: Status filter changed", status)
        window.location.href = status ? `?status=${status}` : "?"
    })

    configureStandardPagination(body.querySelector("div.reports-pagination"))
})
