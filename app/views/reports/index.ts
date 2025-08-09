import { configureStandardPagination } from "../lib/standard-pagination"

const body = document.querySelector("body.reports-body")
if (body) {
    const reportStatusFilter = body.querySelector("select#reportStatusFilter")
    reportStatusFilter.addEventListener("change", () => {
        const status = reportStatusFilter.value
        console.debug("onReportStatusFilterChange", status)
        window.location.href = status ? `?status=${status}` : "?"
    })

    configureStandardPagination(body.querySelector("div.reports-pagination"))
}
