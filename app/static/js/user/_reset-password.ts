import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.reset-password-body")
if (body) {
    // On successful reset request, reset the form
    const resetForm: HTMLFormElement = body.querySelector("form.reset-form")
    configureStandardForm(resetForm, () => {
        resetForm.reset()
    })
}
