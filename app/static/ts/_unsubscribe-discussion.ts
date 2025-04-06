import { Modal } from "bootstrap"
import { configureStandardForm } from "./_standard-form"

const modalElement = document.getElementById("unsubscribeDiscussionModal")
if (modalElement) {
    const modal = new Modal(modalElement, {
        backdrop: "static", // Prevents closing when clicking outside
        keyboard: false,
    })
    modal.show()

    const redirectLink = modalElement.querySelector(".modal-footer a[href]")
    redirectLink.addEventListener("click", () => {
        // On redirect button click, hide the modal
        console.debug("onUnsubscribeRedirect", redirectLink.href)
        modal.hide()
    })

    configureStandardForm(modalElement.querySelector("form.subscription-form"), () => {
        // On success callback, redirect to the discussion page
        console.debug("onUnsubscribeFormSuccess", redirectLink.href)
        window.location.href = redirectLink.href
    })
}
