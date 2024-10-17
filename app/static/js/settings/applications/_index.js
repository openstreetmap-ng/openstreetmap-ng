import { Collapse } from "bootstrap"
import { qsEncode, qsParse } from "../../_qs.js"
import { configureStandardForm } from "../../_standard-form.js"
import { initializeResetSecretControls } from "./_reset-secret-control.js"

const body = document.querySelector("body.settings-applications-body")
if (body) {
    // Fixup links in buttons
    const accordionButtons = body.querySelectorAll(".accordion-button")
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

    // settings/applications + settings/applications/tokens
    const revokeApplicationForms = body.querySelectorAll("form.revoke-application-form")
    for (const form of revokeApplicationForms) {
        const onRevokeApplicationFormSuccess = () => {
            form.closest("li").remove()
        }

        configureStandardForm(form, onRevokeApplicationFormSuccess)
    }

    // settings/applications/admin
    const createApplicationButton = body.querySelector(".create-application-btn")
    if (createApplicationButton) {
        const createApplicationForm = body.querySelector(".create-application-form")

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

    // settings/applications/tokens
    const createForm = body.querySelector("form.create-token-form")
    if (createForm) {
        // On success callback, reload the page
        const onCreateFormSuccess = ({ token_id }) => {
            console.debug("onCreateFormSuccess", token_id)
            const searchParams = qsParse(window.location.search.substring(1))
            searchParams.expand = token_id
            window.location = `${window.location.pathname}?${qsEncode(searchParams)}${window.location.hash}`
        }

        configureStandardForm(createForm, onCreateFormSuccess)
        initializeResetSecretControls()
    }
}
