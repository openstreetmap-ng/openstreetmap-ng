import { t } from "i18next"
import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.traces-details-body")
if (body) {
    const deleteForm = body.querySelector("form.delete-form")
    if (deleteForm) {
        configureStandardForm(deleteForm, ({ redirect_url }) => {
            // On success callback, navigate to my traces
            console.debug("onDeleteFormSuccess", redirect_url)
            window.location.href = redirect_url
        })

        // On delete button click, request confirmation
        const deleteButton = deleteForm.querySelector("button[type=submit]")
        deleteButton.addEventListener("click", (event: Event) => {
            if (!confirm(t("trace.delete_confirmation"))) {
                event.preventDefault()
            }
        })
    }
}
