import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.reset-password-body")
if (body) {
    const resetForm = body.querySelector("form.reset-form")
    configureStandardForm(resetForm, () => {
        // On successful reset request, reset the form
        resetForm.reset()
    })
}
