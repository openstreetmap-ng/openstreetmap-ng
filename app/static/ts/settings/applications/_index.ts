import { Collapse } from "bootstrap"
import { qsEncode, qsParse } from "../../_qs"
import { configureStandardForm } from "../../_standard-form"
import { initializeResetSecretControls } from "./_reset-secret-control"

const body = document.querySelector("body.settings-applications-body")
if (body) {
    // Fixup links in buttons
    const accordionButtons = body.querySelectorAll("button.accordion-button")
    for (const button of accordionButtons) {
        const collapse = document.querySelector(button.dataset.bsTarget)
        const collapseInstance = Collapse.getOrCreateInstance(collapse, { toggle: false })
        // @ts-ignore
        collapseInstance._triggerArray.push(button)

        // On accordion button click, toggle the collapse if target is not a link
        button.addEventListener("click", ({ target }: Event) => {
            const tagName = (target as HTMLElement).tagName
            console.debug("onAccordionButtonClick", tagName)
            if (tagName === "A") return
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
    const createApplicationButton = body.querySelector("button.create-application-btn")
    if (createApplicationButton) {
        const createApplicationForm = body.querySelector("form.create-application-form")

        // On create new application button click, show the form and focus the name input
        createApplicationButton.addEventListener("click", () => {
            console.debug("onCreateNewApplicationClick")
            createApplicationButton.classList.add("d-none")
            createApplicationForm.classList.remove("d-none")
            const nameInput = createApplicationForm.elements.namedItem("name") as HTMLInputElement
            nameInput.focus()
        })

        configureStandardForm(createApplicationForm, ({ redirect_url }) => {
            console.debug("onCreateApplicationFormSuccess", redirect_url)
            window.location.href = redirect_url
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
            window.location.href = `${window.location.pathname}?${qsEncode(searchParams)}${window.location.hash}`
        })

        initializeResetSecretControls()
    }
}
