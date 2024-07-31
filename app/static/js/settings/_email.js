import { configureStandardForm } from "../_standard-form.js"

const settingsEmailBody = document.querySelector("body.settings-email-body")
if (settingsEmailBody) {
    const emailForm = settingsEmailBody.querySelector("form.email-form")

    const onFormSuccess = () => {
        emailForm.reset()
    }

    configureStandardForm(emailForm, onFormSuccess)
}
