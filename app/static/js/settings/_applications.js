import { Collapse } from "bootstrap"
import { configureStandardForm } from "../_standard-form.js"

const settingsApplicationsBody = document.querySelector("body.settings-applications-body")
if (settingsApplicationsBody) {
    // Fixup links in buttons
    const accordionButtons = settingsApplicationsBody.querySelectorAll(".accordion-button")
    for (const button of accordionButtons) {
        const collapse = document.querySelector(button.dataset.bsTarget)
        const collapseInstance = Collapse.getOrCreateInstance(collapse, { toggle: false })
        collapseInstance._triggerArray.push(button)

        const onAccordionButtonClick = (e) => {
            console.debug("onAccordionButtonClick", e.target.tagName)
            if (e.target.tagName === "A") return
            collapseInstance.toggle()
        }

        button.addEventListener("click", onAccordionButtonClick)
    }

    const revokeApplicationForms = settingsApplicationsBody.querySelectorAll("form.revoke-application-form")
    for (const form of revokeApplicationForms) {
        const onRevokeApplicationFormSuccess = () => {
            form.closest("li").remove()
        }

        configureStandardForm(form, onRevokeApplicationFormSuccess)
    }

    const createNewApplicationButton = settingsApplicationsBody.querySelector(".create-new-application-btn")
    if (createNewApplicationButton) {
        const onCreateNewApplicationClick = () => {
            createNewApplicationButton.classList.add("d-none")
            const form = createNewApplicationButton.parentElement.querySelector("form")
            form.classList.remove("d-none")
            form.elements.name.focus()
        }

        createNewApplicationButton.addEventListener("click", onCreateNewApplicationClick)
    }
}
