import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.traces-upload-body")
if (body) {
    const uploadForm = body.querySelector("form.upload-form")
    configureStandardForm(uploadForm, ({ trace_id }) => {
        // On success callback, navigate to the new trace
        console.debug("onUploadFormSuccess", trace_id)
        window.location.href = `/trace/${trace_id}`
    })
}
