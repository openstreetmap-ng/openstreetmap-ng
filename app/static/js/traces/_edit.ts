import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.traces-edit-body")
if (body) {
    const updateForm = body.querySelector("form.update-form")
    configureStandardForm(updateForm, ({ trace_id }) => {
        // On success callback, navigate to the trace details
        console.debug("onUpdateFormSuccess", trace_id)
        window.location.href = `/trace/${trace_id}`
    })
}
