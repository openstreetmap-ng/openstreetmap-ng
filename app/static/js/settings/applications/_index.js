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

        button.addEventListener("click", (e) => {
            console.debug("onAccordionButtonClick", e.target.tagName)
            if (e.target.tagName === "A") return
            collapseInstance.toggle()
        })
    }

    // settings/applications + settings/applications/tokens
    const revokeApplicationForms = body.querySelectorAll("form.revoke-application-form")
    for (const form of revokeApplicationForms) {
        configureStandardForm(form, () => {
            console.debug("onRevokeApplicationFormSuccess")
            form.closest("li").remove()
        })
    }

    // settings/applications/admin
    const createApplicationButton = body.querySelector(".create-application-btn")
    if (createApplicationButton) {
        const createApplicationForm = body.querySelector(".create-application-form")

        createApplicationButton.addEventListener("click", () => {
            console.debug("onCreateNewApplicationClick")
            createApplicationButton.classList.add("d-none")
            createApplicationForm.classList.remove("d-none")
            createApplicationForm.elements.name.focus()
        })

        configureStandardForm(createApplicationForm, ({ redirect_url }) => {
            console.debug("onCreateApplicationFormSuccess", redirect_url)
            window.location = redirect_url
        })
    }

    // settings/applications/tokens
    const createTokenForm = body.querySelector("form.create-token-form")
    if (createTokenForm) {
        configureStandardForm(createTokenForm, ({ token_id }) => {
            // On success callback, reload the page
            console.debug("onCreateTokenFormSuccess", token_id)
            const searchParams = qsParse(window.location.search.substring(1))
            searchParams.expand = token_id
            window.location = `${window.location.pathname}?${qsEncode(searchParams)}${window.location.hash}`
        })
        initializeResetSecretControls()
    }
}
