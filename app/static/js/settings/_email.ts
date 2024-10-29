import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.settings-email-body")
if (body) {
    const emailForm = body.querySelector("form.email-form")
    configureStandardForm(emailForm, () => {
        // On success callback, reset the email change form
        emailForm.reset()
    })
}
