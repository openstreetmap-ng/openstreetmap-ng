import { configureStandardPagination } from "../_standard-pagination"

const body = document.querySelector("body.notes-body")
if (body) {
    const noteStatusFilter = document.querySelector("select#noteStatusFilter")
    noteStatusFilter.addEventListener("change", () => {
        const status = noteStatusFilter.value
        console.debug("onNoteStatusFilterChange", status)
        window.location.href = status ? `?status=${noteStatusFilter.value}` : "?"
    })

    const notes = document.querySelector("div.notes-pagination")
    if (notes) configureStandardPagination(notes)
}
