import { configureStandardForm } from "../_standard-form.js"

const tracesEditBody = document.querySelector("body.traces-edit-body")
if (tracesEditBody) {
    const updateForm = tracesEditBody.querySelector("form.update-form")

    // On success callback, navigate to the trace details
    const onFormSuccess = ({ trace_id }) => {
        window.location = `/trace/${trace_id}`
    }

    configureStandardForm(updateForm, onFormSuccess)
}
