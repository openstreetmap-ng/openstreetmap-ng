import { configureDatetimeInputs } from "../lib/datetime"
import { configureStandardPagination } from "../lib/standard-pagination"

const body = document.querySelector("body.audit-body")
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

    configureStandardPagination(body, { reverse: false })
}
