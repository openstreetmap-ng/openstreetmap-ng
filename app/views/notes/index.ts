import { mount } from "@lib/mount"
import { configureStandardPagination } from "@lib/standard-pagination"

mount("notes-body", (body) => {
    const noteStatusFilter = body.querySelector("select#noteStatusFilter")!
    noteStatusFilter.addEventListener("change", () => {
        const status = noteStatusFilter.value
        console.debug("NotesIndex: Status filter changed", status)
        window.location.href = status ? `?status=${noteStatusFilter.value}` : "?"
    })

    configureStandardPagination(body.querySelector("div.notes-pagination"))
})
