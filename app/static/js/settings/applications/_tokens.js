import { configureStandardForm } from "../../_standard-form.js"

const body = document.querySelector("body.settings-applications-tokens-body")
if (body) {
    const createForm = body.querySelector("form.create-form")

    // On success callback, reload the page
    const onCreateFormSuccess = () => {
        console.debug("onCreateFormSuccess")
        window.location.reload()
    }

    configureStandardForm(createForm, onCreateFormSuccess)
}
