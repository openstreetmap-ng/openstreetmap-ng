import { Modal } from "bootstrap"
import { configureStandardForm } from "./lib/standard-form"

const modalElement = document.getElementById("unsubscribeDiscussionModal")
if (modalElement) {
    const redirectLink = modalElement.querySelector("a.btn-close[href]").href

    modalElement.addEventListener("hide.bs.modal", (e) => {
        e.preventDefault()
        console.debug("onUnsubscribeModalHide", redirectLink)
        window.location.href = redirectLink
    })

    configureStandardForm(modalElement.querySelector("form.subscription-form"), () => {
        // On success callback, redirect to the discussion page
        console.debug("onUnsubscribeFormSuccess", redirectLink)
        window.location.href = redirectLink
    })

    new Modal(modalElement, {
        backdrop: "static", // Prevents closing when clicking outside
    }).show()
}
