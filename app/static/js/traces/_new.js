import { configureStandardForm } from "../_standard-form.js"

const tracesNewBody = document.querySelector('body.traces-new-body')
if (tracesNewBody) {
    const uploadForm = tracesNewBody.querySelector('form.upload-form')

    // On success callback, navigate to the new trace
    const onFormSuccess = ({ trace_id }) => {
        console.debug("onFormSuccess", trace_id)
        location.href = `/traces/${trace_id}`
    }

    configureStandardForm(uploadForm, onFormSuccess)
}
