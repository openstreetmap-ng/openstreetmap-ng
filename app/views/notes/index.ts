import { configureStandardPagination } from "../lib/standard-pagination"

const body = document.querySelector("body.notes-body")
if (body) {
    const noteStatusFilter = body.querySelector("select#noteStatusFilter")
    noteStatusFilter.addEventListener("change", () => {
        const status = noteStatusFilter.value
        console.debug("onNoteStatusFilterChange", status)
        window.location.href = status ? `?status=${noteStatusFilter.value}` : "?"
    })

    configureStandardPagination(body.querySelector("div.notes-pagination"))
}
