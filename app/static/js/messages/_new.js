import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.messages-new-body")
if (body) {
    const messageForm = body.querySelector("form.message-form")
    configureStandardForm(messageForm, ({ redirect_url }) => {
        console.debug("onMessageFormSuccess", redirect_url)
        window.location = redirect_url
    })
}
