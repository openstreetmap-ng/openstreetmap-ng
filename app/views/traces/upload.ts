import { mount } from "@lib/mount"
import { IdResponseSchema } from "@lib/proto/shared_pb"
import { configureStandardForm } from "@lib/standard-form"

mount("traces-upload-body", (body) => {
  configureStandardForm(
    body.querySelector("form.upload-form"),
    (data) => {
      // On success callback, navigate to the new trace
      console.debug("TraceUpload: Success", data.id)
      window.location.href = `/trace/${data.id}`
    },
    { protobuf: IdResponseSchema },
  )
})
