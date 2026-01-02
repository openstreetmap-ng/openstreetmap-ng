import { mount } from "@lib/mount"
import { configureStandardForm } from "@lib/standard-form"

mount("reset-password-body", (body) => {
  const resetForm = body.querySelector("form.reset-form")!
  configureStandardForm(resetForm, () => {
    // On successful reset request, reset the form
    resetForm.reset()
    console.debug("ResetPassword: Request submitted")
  })
})
