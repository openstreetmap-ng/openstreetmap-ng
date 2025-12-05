import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"
import { t } from "i18next"

mount("traces-edit-body", (body) => {
    const updateForm = body.querySelector("form.update-form")
    configureStandardForm(updateForm, ({ trace_id }) => {
        // On success callback, navigate to the trace details
        console.debug("onUpdateFormSuccess", trace_id)
        window.location.href = `/trace/${trace_id}`
    })

    const deleteForm = body.querySelector("form.delete-form")
    configureStandardForm(deleteForm, ({ redirect_url }) => {
        // On success callback, navigate to my traces
        console.debug("onDeleteFormSuccess", redirect_url)
        window.location.href = redirect_url
    })

    const deleteButton = deleteForm.querySelector("button[type=submit]")
    deleteButton.addEventListener("click", (e) => {
        // On delete button click, request confirmation
        if (!confirm(t("trace.delete_confirmation"))) {
            e.preventDefault()
        }
    })
})
