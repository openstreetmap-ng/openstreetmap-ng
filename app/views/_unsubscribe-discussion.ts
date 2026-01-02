import { configureStandardForm } from "@lib/standard-form"
import { Modal } from "bootstrap"

const modalElement = document.getElementById("unsubscribeDiscussionModal")
if (modalElement) {
  const redirectLink = modalElement.querySelector("a.btn-close[href]")!.href

  modalElement.addEventListener("hide.bs.modal", (e) => {
    e.preventDefault()
    console.debug("Unsubscribe: Modal hide", redirectLink)
    window.location.href = redirectLink
  })

  configureStandardForm(modalElement.querySelector("form.subscription-form"), () => {
    // On success callback, redirect to the discussion page
    console.debug("Unsubscribe: Success", redirectLink)
    window.location.href = redirectLink
  })

  new Modal(modalElement, {
    backdrop: "static", // Prevents closing when clicking outside
  }).show()
}
