import { configureDatetimeInputs } from "@lib/datetime-inputs"
import { mount } from "@lib/mount"
import { configureStandardPagination } from "@lib/standard-pagination"
import { configureUserAgentIcons } from "@lib/user-agent-icons"

mount("audit-body", (body) => {
    const filterForm = body.querySelector("form.filters-form")!

    // Setup datetime input timezone conversion
    configureDatetimeInputs(filterForm, ["created_after", "created_before"])

    // Disable empty inputs before form submission to prevent validation errors
    filterForm.addEventListener("submit", () => {
        const inputs = filterForm.querySelectorAll("input, select")
        for (const input of inputs) {
            if (!input.value) input.disabled = true
        }
    })

    configureStandardPagination(body, {
        reverse: false,
        loadCallback: (renderContainer) => {
            configureUserAgentIcons(renderContainer)

            for (const button of renderContainer.querySelectorAll(
                "button[data-app-id]",
            )) {
                button.addEventListener("click", (e) => {
                    e.preventDefault()
                    filterForm.querySelector("input[name=application_id]")!.value =
                        button.dataset.appId!
                    filterForm.requestSubmit()
                })
            }
        },
    })
})
