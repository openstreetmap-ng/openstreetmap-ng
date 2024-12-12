import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.reset-password-token-body")
if (body) {
    const resetForm = body.querySelector("form.reset-form")
    configureStandardForm(resetForm, () => {
        // On successful reset request, update the form state
        resetForm.reset()
        resetForm.querySelector(".before").remove()
        resetForm.querySelector(".after").classList.remove("d-none")
    })
}
