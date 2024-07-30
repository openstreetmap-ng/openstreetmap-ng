import { t } from "i18next"
import { configureStandardForm } from "../_standard-form.js"

const tracesDetailsBody = document.querySelector("body.traces-details-body")
if (tracesDetailsBody) {
    const deleteForm = tracesDetailsBody.querySelector("form.delete-form")
    if (deleteForm) {
        const deleteButton = deleteForm.querySelector('button[type="submit"]')

        // On button click, request confirmation
        const onDeleteClick = (event) => {
            if (!confirm(t("traces.show.confirm_delete"))) {
                event.preventDefault()
            }
        }

        // On success callback, navigate to my traces
        const onFormSuccess = ({ redirect_url }) => {
            console.debug("onFormSuccess", redirect_url)
            window.location = redirect_url
        }

        configureStandardForm(deleteForm, onFormSuccess)
        deleteButton.addEventListener("click", onDeleteClick)
    }
}
