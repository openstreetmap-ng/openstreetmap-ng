import { Collapse } from "bootstrap"
import { configureStandardForm } from "../../_standard-form.js"

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

    const createApplicationButton = settingsApplicationsBody.querySelector(".create-application-btn")
    if (createApplicationButton) {
        const createApplicationForm = settingsApplicationsBody.querySelector(".create-application-form")

        const onCreateNewApplicationClick = () => {
            createApplicationButton.classList.add("d-none")
            createApplicationForm.classList.remove("d-none")
            createApplicationForm.elements.name.focus()
        }

        const onCreateApplicationFormSuccess = ({ redirect_url }) => {
            console.debug("onCreateApplicationFormSuccess", redirect_url)
            window.location = redirect_url
        }

        createApplicationButton.addEventListener("click", onCreateNewApplicationClick)
        configureStandardForm(createApplicationForm, onCreateApplicationFormSuccess)
    }
}
