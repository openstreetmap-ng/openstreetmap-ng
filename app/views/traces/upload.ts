import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"

mount("traces-upload-body", (body) => {
    configureStandardForm(body.querySelector("form.upload-form"), ({ trace_id }) => {
        // On success callback, navigate to the new trace
        console.debug("onUploadFormSuccess", trace_id)
        window.location.href = `/trace/${trace_id}`
    })
})
