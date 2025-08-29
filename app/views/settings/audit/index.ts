import { configureStandardPagination } from "../../lib/standard-pagination"

const body = document.querySelector("body.settings-audit-body")
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
}
