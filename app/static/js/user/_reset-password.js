import { configureStandardForm } from "../_standard-form.js"

const resetPasswordBody = document.querySelector("body.reset-password-body")
if (resetPasswordBody) {
    const resetForm = resetPasswordBody.querySelector("form.reset-form")

    const onSignupSuccess = () => {
        resetForm.reset()
    }

    configureStandardForm(resetForm, onSignupSuccess)
}
