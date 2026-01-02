import { mount } from "@lib/mount"
import { IdResponseSchema } from "@lib/proto/shared_pb"
import { configureStandardForm } from "@lib/standard-form"
import { t } from "i18next"

mount("traces-edit-body", (body) => {
  const updateForm = body.querySelector("form.update-form")
  configureStandardForm(
    updateForm,
    (data) => {
      // On success callback, navigate to the trace details
      console.debug("TraceEdit: Updated", data.id)
      window.location.href = `/trace/${data.id}`
    },
    { protobuf: IdResponseSchema },
  )

  const deleteForm = body.querySelector("form.delete-form")!
  configureStandardForm(deleteForm, ({ redirect_url }) => {
    // On success callback, navigate to my traces
    console.debug("TraceEdit: Deleted", redirect_url)
    window.location.href = redirect_url
  })

  const deleteButton = deleteForm.querySelector("button[type=submit]")!
  deleteButton.addEventListener("click", (e) => {
    // On delete button click, request confirmation
    if (!confirm(t("trace.delete_confirmation"))) {
      e.preventDefault()
    }
  })
})
